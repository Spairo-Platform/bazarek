---
name: gdzie-tracisz-limit
description: Pokazuje w kilku linijkach, ile limitu użytkownik traci przez długą historię rozmów i wznowienia po przerwie, w których rozmowach najwięcej i jak to się zmienia w ostatnich tygodniach. Działa w Claude Code i w Codexie. Użyj, gdy ktoś pyta, czemu nie prowadzić wszystkiego w jednym wątku, dlaczego szybko kończy mu się limit, ile traci na powrotach do starych rozmów albo gdzie ucieka mu limit.
---

# Gdzie tracisz limit

Odbiorca jest zwykle nietechniczny, np. uczestnik szkolenia. Odpowiedź ma być **krótka**: wynik skryptu, najwyżej jedna rada i krótki komentarz do trendu. Bez wstępów, bez wyjaśniania metody, bez żargonu (cache, kontekst). Słowo „token” tylko z wyjaśnieniem, że to kawałek tekstu, którym AI mierzy długość rozmowy. Nazwy strat: „długa historia rozmowy” i „wznowienia po przerwie”.

Skrypt leży w folderze tego skilla: `scripts/gdzie_tracisz_limit.py`. Uruchamiaj go pełną ścieżką, np. `python3 -I <folder skilla>/scripts/gdzie_tracisz_limit.py`. Czyta tylko lokalne logi na tym komputerze i niczego nie wysyła.

**Źródło logów.** W Claude Code skrypt sam czyta logi Claude Code. **W Codexie zawsze dodawaj `--zrodlo codex`.** `--zrodlo oba` łączy oba źródła, tylko gdy ktoś o to poprosi.

## Wariant interaktywny (tylko Claude, gdy jest narzędzie `show_widget`)

Gdy masz narzędzie `mcp__visualize__show_widget` (także jako narzędzie odroczone, które trzeba załadować), pokaż komponent z suwakiem zamiast tekstu. Użytkownik sam ustawia suwakiem „Rozmowa najwyżej do” i widzi osobno straty od długiej historii i od wznowień po przerwie, top 5 rozmów i trend 4 tygodni.

1. Wywołaj `mcp__visualize__read_me` z `modules: ["interactive"]` (wymagane przed pierwszym `show_widget`; nie wspominaj o tym użytkownikowi).
2. Uruchom skrypt z `--widget` i przekaż cały wynik **bez zmian** jako `widget_code` do `show_widget` (title: `gdzie_tracisz_limit`). Komponent domyślnie pokazuje ostatnie 4 tygodnie. `--days` i `--project` działają tak samo jak w wersji tekstowej.
3. Pod komponentem napisz najwyżej dwa zdania: werdykt dla domyślnego ustawienia suwaka (200 tys., ok. 350 stron) (z karty „Razem”: poniżej 10% → nie ma co walczyć, poniżej 25% → warto poprawić, wyżej → dużo do odzyskania) i jedną radę z listy niżej. Liczb z komponentu nie powtarzaj.

W Codexie i wszędzie, gdzie tego narzędzia nie ma, użyj wariantu tekstowego.

## Wariant tekstowy

1. Uruchom skrypt bez dodatkowych opcji (w Codexie z `--zrodlo codex`). Domyślnie analizuje ostatnie 7 dni i dodaje linię trendu z 4 tygodni. Opcje: `--days 30` albo `--days 0` (cała historia), `--project TEKST` (tylko jeden folder projektu), `--szczegoly` (lista wszystkich wznowień po przerwie, tylko na wyraźną prośbę).
2. Wklej wynik skryptu **bez zmian**. To gotowy Markdown: werdykt, „Dlaczego”, tabelka top 3, trend.
3. Dopisz **jedną** radę (jedno, dwa zdania), dobraną do wyniku:
   - w tabelce dominują **wznowienia po przerwie** → „Kończysz dzień w dużym wątku? Ostatnia wiadomość: »podsumuj, na czym skończyliśmy i co dalej«. Jutro zacznij od tego nowy wątek.”
   - dominuje **długa historia rozmowy** → „Nowy temat to nowy wątek. Gdy rozmowa zeszła na coś innego, poproś o podsumowanie i przejdź z nim do nowego wątku.”
   - **zmiana modelu w trakcie** → „Model wybieraj na początku rozmowy, nie w jej środku.”
   - werdykt **NIE MA CO WALCZYĆ** → bez rady, najwyżej „tak trzymaj”.
4. Jeśli trend maleje albo rośnie, możesz to skomentować kilkoma słowami. Nie dopisuj nic o dobijaniu do limitu, bo wynik skryptu już to mówi.

Nie podawaj procentów limitu tygodniowego i nie odczytuj limitu żadnym narzędziem. Logi nie widzą rozmów w przeglądarce ani dodatkowych resetów limitu, więc takie przeliczenie byłoby mylące. „Na ile dni dłużej starczałby limit” wynika z samego udziału strat.

Skill widzi tylko rozmowy z Claude Code (zakładka Code w aplikacji i terminal) albo z Codexa. Nie widzi claude.ai ani ChatGPT w przeglądarce. Jeśli wynik to „Brak rozmów”, powiedz, że kto pracuje głównie w przeglądarce, musi tam pilnować tych samych nawyków.

## Gdy ktoś dopytuje o mechanizm (tylko wtedy)

- Przy każdej wiadomości model czyta od nowa całą rozmowę, więc w długim wątku każda wiadomość kosztuje więcej.
- Przez jakiś czas rozmowa jest w szybkiej pamięci, gdzie czytanie jest tanie (Claude: ok. godzinę). Po dłuższej przerwie albo po zmianie modelu wczytuje się od nowa: w Claude ok. 20× drożej, w Codexie ok. 10× drożej.
- Prośba o podsumowanie po przerwie też wymaga takiego wczytania. Opłaca się mimo to, jeśli planujesz więcej niż jedno, dwa pytania, bo każda następna wiadomość w nowym wątku jest kilka razy tańsza. Najtaniej jest zrobić podsumowanie przed przerwą.
- Przy dłuższej pracy najlepszy nawyk to plik z postępami (np. `notatki.md`), który model uzupełnia na bieżąco. Nowa sesja czyta tylko ten plik.

## Jak liczy skrypt (dla Ciebie)

- Zużycie każdej wiadomości jest ważone proporcjami cen API. Claude: odczyt z pamięci podręcznej 0,1, zapis 2, zwykłe wejście 1, odpowiedź 5. Codex: odczyt 0,1, wejście 1 (zapis bez dopłaty), odpowiedź 8.
- Długa historia rozmowy: odczyt rozmowy ponad 200 tys. × 0,1 (`--prog-watku`). Sama sesja ma ok. 50 tys. na starcie, więc niższy próg karałby normalną pracę.
- Wznowienie po przerwie: wiadomość, przy której ponad połowę poprzedniej rozmowy trzeba było wczytać od nowa. Strata to różnica między tym wczytaniem a tanim odczytem. W Codexie liczone tylko po przerwie od 5 min albo po zmianie modelu, bo OpenAI gubi pamięć podręczną także bez przerwy, a na to nawyk nie pomoże.
- Werdykt według udziału strat w zużyciu: poniżej 10% → NIE MA CO WALCZYĆ, poniżej 25% → WARTO POPRAWIĆ, wyżej → DUŻO DO ODZYSKANIA. „Dni dłużej” = 7 × udział / (1 − udział), pokazywane tylko od 10% strat i z zastrzeżeniem „jeśli dobijasz do limitu”.
- Trend: udział strat w kolejnych 7-dniowych oknach. Tygodnie z bardzo małym zużyciem są pokazane jako „–”.
- Rozmowy rozgałęzione nie są liczone podwójnie, a subagenci są doliczani do rozmowy, z której ich wywołano.
