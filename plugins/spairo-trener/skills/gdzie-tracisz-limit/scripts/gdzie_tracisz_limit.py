#!/usr/bin/env python3
"""Gdzie tracisz limit: długa historia rozmów i wznowienia po przerwie.

Czyta lokalne logi Claude Code (~/.claude/projects) albo Codexa (~/.codex/sessions)
i liczy dwa źródła strat:
  1. długa historia rozmowy: każda wiadomość czyta całą dotychczasową rozmowę, więc im
     dłuższy wątek, tym droższa każda kolejna wiadomość;
  2. wznowienie po przerwie: po dłuższej przerwie (albo po zmianie modelu) cała rozmowa
     wczytuje się od nowa, bez taniej pamięci podręcznej.

Wynik jest względny (udział w Twoim zużyciu). Nie przelicza na % limitu, bo
logi nie widzą rozmów w przeglądarce ani dodatkowych resetów limitu.
Nic nie jest wysyłane: skrypt tylko czyta pliki na tym komputerze.

Użycie:
  python3 -I gdzie_tracisz_limit.py [--zrodlo auto|claude|codex|oba] [--days 7] [--tygodnie 4] [--widget]
"""
import argparse, glob, json, os, sys
from datetime import datetime, timedelta, timezone

# Mnożniki ceny względem zwykłego wejścia (proporcje z cennika API).
CENA_READ = 0.1
CENA_WRITE = 2.0  # zapis do pamięci podręcznej z TTL 1 h
WAGI = {"input_tokens": 1.0, "cache_creation_input_tokens": CENA_WRITE,
        "cache_read_input_tokens": CENA_READ, "output_tokens": 5.0}
# OpenAI: zapis do pamięci podręcznej nie ma dopłaty, odpowiedź ok. 8× droższa od wejścia.
WAGI_CODEX = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.0,
              "cache_read_input_tokens": CENA_READ, "output_tokens": 8.0}
KROTKI = 100_000  # „krótki wątek” jako punkt odniesienia dla ceny wiadomości


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt(n):
    return f"{int(round(n)):,}".replace(",", " ")


def tys(n):
    return f"{n / 1000:.0f} tys." if n < 1_000_000 else f"{n / 1e6:.1f} mln".replace(".", ",")


def pl(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def przerwa_txt(m):
    if m < 120:
        return f"{m:.0f} min"
    if m < 48 * 60:
        return f"{m / 60:.0f} h"
    return f"{pl(m / 1440)} dni"


def tekst(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                return c.get("text", "")
    return ""


def wagi(u):
    return u.get("_wagi") or WAGI


def skroc(t, n=50):
    t = " ".join(t.split())
    return t if len(t) <= n else t[:n].rstrip() + "…"


def koszt(u):
    return sum((u.get(k, 0) or 0) * w for k, w in wagi(u).items())


def strata_wczytania(u):
    """Ile więcej kosztowało wczytanie rozmowy od nowa niż tani odczyt z pamięci."""
    g = wagi(u)
    return ((u.get("cache_creation_input_tokens", 0) or 0) * (g["cache_creation_input_tokens"] - CENA_READ)
            + (u.get("input_tokens", 0) or 0) * (g["input_tokens"] - CENA_READ))


def kontekst(u):
    return sum(u.get(k, 0) or 0 for k in
               ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


# ---------- wczytywanie ----------

def wczytaj_sesje(root):
    """sid -> sesja. Każde wywołanie modelu liczone raz (rozmowy rozgałęzione dzielą
    historię; przypisujemy je do najstarszego pliku). Subagenci doliczani do rozmowy-rodzica."""
    widziane, sesje = set(), {}
    pliki = sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True),
                   key=os.path.getmtime)
    for p in pliki:
        rel = os.path.relpath(p, root).split(os.sep)
        if len(rel) < 2:
            continue
        sub = len(rel) > 2  # <proj>/<sid>/subagents/<plik>.jsonl
        sid = rel[1] if sub else rel[1][:-6]
        s = sesje.setdefault(sid, {"sid": sid, "proj": rel[0], "tytul": None, "pierwsze": None,
                                   "glowny": [], "sub": []})
        with open(p, errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                t = d.get("type")
                if t == "custom-title" and not sub:
                    s["tytul"] = d.get("customTitle") or s["tytul"]
                elif t == "user" and not sub and s["pierwsze"] is None and not d.get("isMeta"):
                    txt = tekst((d.get("message") or {}).get("content")).strip()
                    if txt and not txt.startswith("<"):
                        s["pierwsze"] = txt
                elif t == "assistant":
                    m = d.get("message") or {}
                    u, mid, czas = m.get("usage"), m.get("id"), d.get("timestamp")
                    if not u or not czas or mid in widziane or m.get("model") == "<synthetic>":
                        continue
                    widziane.add(mid)
                    rek = (ts(czas), u, m.get("model"))
                    (s["sub"] if sub or d.get("isSidechain") else s["glowny"]).append(rek)
    for s in sesje.values():
        s["glowny"].sort(key=lambda x: x[0])
        s["nazwa"] = s["tytul"] or skroc(s["pierwsze"] or "") or "(bez tytułu)"
    return {k: v for k, v in sesje.items() if v["glowny"] or v["sub"]}


def wczytaj_codex(root):
    """Sesje Codexa: ~/.codex/sessions/RRRR/MM/DD/rollout-*.jsonl. Jedno wywołanie modelu
    to jeden rekord token_usage_record (starsze wersje: event_msg token_count).
    Subagenci (session_meta.source.subagent) są doliczani do wątku-rodzica."""
    tytuly = {}
    idx = os.path.join(os.path.dirname(root.rstrip(os.sep)), "session_index.jsonl")
    if os.path.exists(idx):
        for line in open(idx, errors="ignore"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("id") and d.get("thread_name"):
                tytuly[d["id"]] = d["thread_name"]
    widziane, sesje = set(), {}
    for p in sorted(glob.glob(os.path.join(root, "**", "rollout-*.jsonl"), recursive=True)):
        meta, model, rek, rek_tc, pierwsze = {}, None, [], [], None
        with open(p, errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                t, pl_ = d.get("type"), d.get("payload") or {}
                if t == "session_meta" and not meta:
                    meta = pl_
                elif t == "turn_context":
                    model = pl_.get("model") or model
                elif t == "response_item" and pierwsze is None and pl_.get("type") == "message" \
                        and pl_.get("role") == "user":
                    for c in pl_.get("content") or []:
                        txt = (c.get("text") or "").strip() if isinstance(c, dict) else ""
                        if txt and not txt.startswith("<") and not txt.startswith("#"):
                            pierwsze = txt
                            break
                elif t == "token_usage_record":
                    rid = pl_.get("response_id")
                    if rid in widziane:
                        continue
                    widziane.add(rid)
                    rek.append((d.get("timestamp"), pl_.get("usage") or {}, model))
                elif t == "event_msg" and pl_.get("type") == "token_count":
                    lu = ((pl_.get("info") or {}).get("last_token_usage")) or {}
                    if lu:
                        rek_tc.append((d.get("timestamp"), lu, model))
        if not meta:
            continue
        rek = rek or rek_tc
        wid = meta.get("id")
        sid = meta.get("parent_thread_id") or meta.get("session_id") or wid
        sub = sid != wid
        s = sesje.setdefault(sid, {"sid": sid, "proj": meta.get("cwd") or "", "tytul": None,
                                   "pierwsze": None, "glowny": [], "sub": []})
        if not sub:
            s["tytul"] = tytuly.get(wid) or s["tytul"]
            s["pierwsze"] = s["pierwsze"] or pierwsze
            s["proj"] = meta.get("cwd") or s["proj"]
        for czas, u, mod in rek:
            if not czas:
                continue
            wej, cache = u.get("input_tokens", 0) or 0, u.get("cached_input_tokens", 0) or 0
            zap = u.get("cache_write_input_tokens", 0) or 0
            n = {"input_tokens": max(0, wej - cache - zap), "cache_creation_input_tokens": zap,
                 "cache_read_input_tokens": cache, "output_tokens": u.get("output_tokens", 0) or 0,
                 "_wagi": WAGI_CODEX}
            (s["sub"] if sub else s["glowny"]).append((ts(czas), n, mod))
    for s in sesje.values():
        s["glowny"].sort(key=lambda x: x[0])
        s["nazwa"] = s["tytul"] or skroc(s["pierwsze"] or "") or "(bez tytułu)"
    return {k: v for k, v in sesje.items() if v["glowny"] or v["sub"]}


# ---------- analiza ----------

def powroty(seq, min_ctx, prog):
    """Wywołania, w których większość poprzedniej rozmowy trzeba było wczytać od nowa."""
    out, prev_ctx, prev_t, prev_mod = [], None, None, None
    for t, u, mod in seq:
        w = (u.get("cache_creation_input_tokens", 0) or 0) + (u.get("input_tokens", 0) or 0)
        przerwa = (t - prev_t).total_seconds() / 60 if prev_t else 0
        zmiana = bool(prev_mod and mod and mod != prev_mod)
        # Codex (OpenAI) gubi pamięć podręczną także bez przerwy; tego nawyk nie zmieni.
        codex_bez_przerwy = u.get("_wagi") is WAGI_CODEX and przerwa < 5 and not zmiana
        if prev_ctx and prev_ctx >= min_ctx and w > prog * prev_ctx and not codex_bez_przerwy:
            out.append({"czas": t, "przerwa_min": przerwa, "zapis": w,
                        "model": zmiana,
                        "strata": strata_wczytania(u)})
        prev_ctx, prev_t, prev_mod = kontekst(u), t, mod
    return out


def analizuj(sesje, od, do, a):
    """Straty w oknie [od, do)."""
    w = {"koszt": 0.0, "dlugi": 0.0, "powrot": 0.0, "n_powrot": 0, "sesje": [],
         "krotkie": [0, 0.0], "bardzo_dlugie": [0, 0.0]}
    for s in sesje.values():
        k = dl = 0.0
        max_ctx = 0
        for t, u, _ in s["glowny"] + s["sub"]:
            if not (od <= t < do):
                continue
            c, ctx = koszt(u), kontekst(u)
            k += c
            dl += max(0, (u.get("cache_read_input_tokens", 0) or 0) - a.prog_watku) * CENA_READ
            max_ctx = max(max_ctx, ctx)
            if ctx < KROTKI:
                w["krotkie"][0] += 1; w["krotkie"][1] += c
            elif ctx >= 500_000:
                w["bardzo_dlugie"][0] += 1; w["bardzo_dlugie"][1] += c
        if not k:
            continue
        pw = [x for x in powroty(s["glowny"], a.min_context, a.threshold) if od <= x["czas"] < do]
        pc = sum(x["strata"] for x in pw)
        w["koszt"] += k; w["dlugi"] += dl; w["powrot"] += pc; w["n_powrot"] += len(pw)
        w["sesje"].append({**s, "koszt": k, "dlugi": dl, "powrot": pc, "powroty": pw,
                           "max_ctx": max_ctx, "strata": dl + pc})
    w["sesje"].sort(key=lambda x: x["strata"], reverse=True)
    w["udzial"] = (w["dlugi"] + w["powrot"]) / w["koszt"] if w["koszt"] else 0.0
    return w


PROGI = list(range(50_000, 600_001, 25_000))


def dane_json(sesje, teraz, a):
    """Dane dla komponentu z suwakiem: straty od długości wątku policzone dla każdego
    progu z PROGI, osobno straty od powrotów; ostatnie 7 dni i trend tygodniowy."""
    def okno(od, do):
        out, koszt_sum, krotkie = [], 0.0, [0, 0.0]
        for s in sesje.values():
            k, dl, mx = 0.0, [0.0] * len(PROGI), 0
            for t, u, _ in s["glowny"] + s["sub"]:
                if not (od <= t < do):
                    continue
                c, ctx = koszt(u), kontekst(u)
                k += c
                mx = max(mx, ctx)
                r = u.get("cache_read_input_tokens", 0) or 0
                for i, pr in enumerate(PROGI):
                    if r <= pr:
                        break
                    dl[i] += (r - pr) * CENA_READ
                if ctx < KROTKI:
                    krotkie[0] += 1; krotkie[1] += c
            if not k:
                continue
            pw = [x for x in powroty(s["glowny"], a.min_context, a.threshold) if od <= x["czas"] < do]
            koszt_sum += k
            out.append({"n": s["nazwa"], "k": round(k), "mx": mx, "pw": len(pw),
                        "pc": round(sum(x["strata"] for x in pw)), "dl": [round(x) for x in dl]})
        return {"koszt": round(koszt_sum), "sesje": out,
                "sr_krotka": round(krotkie[1] / krotkie[0]) if krotkie[0] else None}

    tyg = []
    for i in range(a.tygodnie - 1, -1, -1):
        do = teraz - timedelta(days=7 * i)
        o = okno(do - timedelta(days=7), do)
        tyg.append({"etykieta": (do - timedelta(days=7)).astimezone().strftime("%d.%m"),
                    "koszt": o["koszt"], "pc": sum(x["pc"] for x in o["sesje"]),
                    "dl": [sum(x["dl"][j] for x in o["sesje"]) for j in range(len(PROGI))]})
    teraz_okno = okno(teraz - timedelta(days=a.days or 36500), teraz)
    teraz_okno["pc"] = sum(x["pc"] for x in teraz_okno["sesje"])
    teraz_okno["dl"] = [sum(x["dl"][j] for x in teraz_okno["sesje"]) for j in range(len(PROGI))]
    teraz_okno["sesje"] = sorted(teraz_okno["sesje"], key=lambda x: -(x["pc"] + max(x["dl"])))[:40]
    return {"progi": PROGI, "domyslny": a.prog_watku, "dni": a.days, "okres": teraz_okno, "tygodnie": tyg,
            "cena_powrotu": CENA_POWROTU, "zrodlo": ZRODLO}


def werdykt(udzial):
    if udzial < 0.10:
        return "NIE MA CO WALCZYĆ"
    return "WARTO POPRAWIĆ" if udzial < 0.25 else "DUŻO DO ODZYSKANIA"


def dni_dluzej(udzial):
    """O ile dni dłużej starczałby tygodniowy limit bez tych strat."""
    return 7 * udzial / (1 - udzial) if udzial < 1 else 0


# ---------- raport (Markdown, gotowy do wklejenia) ----------

def raport(w, a, teraz):
    if not w["koszt"]:
        print("Brak rozmów w wybranym okresie.")
        return
    u = w["udzial"]
    okres = "w ostatnim tygodniu" if a.days == 7 else (f"w ostatnich {a.days} dniach" if a.days else "w całej historii")
    zdanie = (" To niewiele, nawyków nie trzeba zmieniać." if u < 0.10 else
              f" Jeśli dobijasz do tygodniowego limitu, bez tych strat starczałby Ci "
              f"na ok. **{pl(dni_dluzej(u))} dnia dłużej**.")
    print(f"**Werdykt: {werdykt(u)}.** {okres.capitalize()} ok. **{u:.0%}** Twojego zużycia poszło na "
          f"długą historię rozmów i wznowienia po przerwie.{zdanie}")

    kr, bd = w["krotkie"], w["bardzo_dlugie"]
    if kr[0] >= 10:
        sr = kr[1] / kr[0]
        czesci = []
        if bd[0] >= 5:
            czesci.append(f"wiadomość w bardzo długiej rozmowie kosztuje {pl(bd[1] / bd[0] / sr)}× tyle co w krótkiej")
        czesci.append(f"wznowienie po przerwie rozmowy o długości 300 tys. kosztuje tyle co ~{300_000 * CENA_POWROTU / sr:.0f} "
                      f"zwykłych wiadomości")
        print(f"\nDlaczego: {', a '.join(czesci)}.")

    top = [s for s in w["sesje"][: a.top] if s["strata"] >= 0.01 * w["koszt"]]
    if top:
        print("\n| Gdzie uciekło najwięcej | Strata | Dlaczego |\n|---|---|---|")
        for s in top:
            powody = []
            if s["max_ctx"] > a.prog_watku:
                powody.append(f"rozmowa urosła do {tys(s['max_ctx'])}")
            pp = [x for x in s["powroty"] if not x["model"]]
            if pp:
                powody.append(f"{len(pp)}× wznowienie po przerwie")
            if any(x["model"] for x in s["powroty"]):
                powody.append("zmiana modelu w trakcie")
            print(f"| {s['nazwa']} | {s['strata'] / w['koszt']:.0%} zużycia | {', '.join(powody)} |")

    if a.tygodnie > 1:
        tyg = []
        for i in range(a.tygodnie - 1, -1, -1):
            do = teraz - timedelta(days=7 * i)
            tyg.append(analizuj(SESJE, do - timedelta(days=7), do, a))
        maks = max(t["koszt"] for t in tyg) or 1
        etyk = [f"{t['udzial']:.0%}" if t["koszt"] >= 0.1 * maks else "–" for t in tyg]
        ok = [t["udzial"] for t in tyg if t["koszt"] >= 0.1 * maks]
        trend = ""
        if len(ok) >= 3:
            pol = len(ok) // 2
            r = sum(ok[-pol:]) / pol - sum(ok[:pol]) / pol
            trend = " (rośnie)" if r > 0.05 else " (maleje)" if r < -0.05 else " (bez zmian)"
        print(f"\nOstatnie {a.tygodnie} tygodnie, od najstarszego: {' → '.join(etyk)}{trend}")


def szczegoly(w):
    for s in w["sesje"]:
        if not s["powroty"]:
            continue
        print(f"■ {s['nazwa']} | sesja {s['sid'][:8]} | maks. {tys(s['max_ctx'])}")
        for x in s["powroty"]:
            lok = x["czas"].astimezone().strftime("%Y-%m-%d %H:%M")
            print(f"    {lok}  po przerwie {przerwa_txt(x['przerwa_min']):>8}  wczytano {fmt(x['zapis']):>9}"
                  + ("  zmiana modelu" if x["model"] else ""))


def main():
    global SESJE
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None,
                    help="okres głównego wyniku w dniach (0 = cała historia); domyślnie 7, w komponencie tyle co trend")
    ap.add_argument("--tygodnie", type=int, default=4, help="ile tygodni w linii trendu (0 = bez trendu)")
    ap.add_argument("--prog-watku", type=int, default=200_000,
                    help="od jakiej długości wątek uznajemy za przerośnięty")
    ap.add_argument("--top", type=int, default=3, help="ile rozmów w tabelce")
    ap.add_argument("--szczegoly", action="store_true", help="lista wszystkich powrotów po przerwie")
    ap.add_argument("--json", action="store_true", help="dane dla interaktywnego komponentu")
    ap.add_argument("--widget", action="store_true", help="gotowy kod komponentu z suwakiem (HTML z danymi)")
    ap.add_argument("--project", help="fragment nazwy folderu projektu")
    ap.add_argument("--min-context", type=int, default=20_000)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--zrodlo", choices=["auto", "claude", "codex", "oba"], default="auto",
                    help="czyje logi czytać; auto = Claude Code, gdy skrypt działa w Claude Code, inaczej Codex")
    ap.add_argument("--root", help="folder z logami Claude Code (domyślnie ~/.claude/projects)")
    ap.add_argument("--codex-root", help="folder z logami Codexa (domyślnie $CODEX_HOME/sessions albo ~/.codex/sessions)")
    a = ap.parse_args()
    global ZRODLO, CENA_POWROTU
    a.root = a.root or os.path.expanduser("~/.claude/projects")
    a.codex_root = a.codex_root or os.path.join(os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex"), "sessions")
    if a.zrodlo == "auto":
        if os.environ.get("CLAUDECODE") or not os.path.isdir(a.codex_root):
            a.zrodlo = "claude"
        else:
            a.zrodlo = "codex"
    ZRODLO = a.zrodlo
    CENA_POWROTU = 1.0 - CENA_READ if a.zrodlo == "codex" else CENA_WRITE - CENA_READ

    if a.days is None:
        a.days = 7 * a.tygodnie if (a.widget or a.json) and a.tygodnie else 7
    SESJE = {}
    if a.zrodlo in ("claude", "oba") and os.path.isdir(a.root):
        SESJE.update(wczytaj_sesje(a.root))
    if a.zrodlo in ("codex", "oba") and os.path.isdir(a.codex_root):
        for k, v in wczytaj_codex(a.codex_root).items():
            if a.zrodlo == "oba":
                v["nazwa"] += " (Codex)"
            SESJE["codex:" + k] = v
    if a.project:
        SESJE = {k: v for k, v in SESJE.items() if a.project.lower() in v["proj"].lower()}
    teraz = datetime.now(timezone.utc)
    if a.widget:
        sz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "komponent.html")
        dane = json.dumps(dane_json(SESJE, teraz + timedelta(seconds=1), a), ensure_ascii=False,
                          separators=(",", ":")).replace("</", "<\\/")
        sys.stdout.write(open(sz, encoding="utf-8").read().replace("/*DANE*/null", dane))
        return
    if a.json:
        json.dump(dane_json(SESJE, teraz + timedelta(seconds=1), a), sys.stdout, ensure_ascii=False,
                  separators=(",", ":"))
        return
    od = teraz - timedelta(days=a.days) if a.days else datetime.min.replace(tzinfo=timezone.utc)
    w = analizuj(SESJE, od, teraz + timedelta(seconds=1), a)
    raport(w, a, teraz + timedelta(seconds=1))
    if a.szczegoly:
        print()
        szczegoly(w)


SESJE = {}
ZRODLO = "claude"
CENA_POWROTU = CENA_WRITE - CENA_READ

if __name__ == "__main__":
    sys.exit(main())
