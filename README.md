# BazAreK

Otwarte pluginy Spairo do pracy z AI. Działają w **Claude Code** i w **Codexie**.

## Instalacja

Najpierw dodaj marketplace, potem instaluj z niego pluginy.

**Claude Code**

```bash
claude plugin marketplace add Spairo-Platform/bazarek
```

```bash
claude plugin install bazarek@bazarek
```

**Codex**

```bash
codex plugin marketplace add Spairo-Platform/bazarek
```

```bash
codex plugin add bazarek@bazarek
```

Możesz też zainstalować pluginy z listy pluginów w aplikacji Codex.

## Pluginy

### BazAreK (`bazarek`)

Skille, które patrzą, jak pracujesz z AI, i podpowiadają, co zmienić.

#### `gdzie-trace-limit`

Pokazuje, jaka część Twojego zużycia idzie na dwie rzeczy, których da się uniknąć:

- **długa historia rozmowy**: przy każdej wiadomości AI czyta od nowa całą rozmowę, więc w długim wątku każda wiadomość kosztuje więcej;
- **wznowienia po przerwie**: po dłuższej przerwie albo zmianie modelu cała rozmowa wczytuje się od nowa, kilkanaście razy drożej niż zwykle.

Dostajesz werdykt, top rozmowy, w których uciekło najwięcej, i trend z ostatnich 4 tygodni. W aplikacjach Claude i Codex wynik jest interaktywny: suwakiem ustawiasz, jak długie rozmowy chcesz prowadzić, i od razu widzisz, ile byś zaoszczędził(a).

Zapytaj po prostu: „Gdzie tracę limit?” albo „Czemu tak szybko kończy mi się limit?”. W Claude Code skill wywołasz też wprost: `/bazarek:gdzie-trace-limit`.

**Prywatność.** Skrypt czyta tylko lokalne logi na Twoim komputerze (`~/.claude/projects` albo `~/.codex/sessions`) i niczego nie wysyła. Do działania wystarczy Python 3, bez dodatkowych bibliotek.

**Ograniczenia.**

- Działa tylko w Claude Code i Codexie na Twoim komputerze (aplikacja desktop lub terminal). W przeglądarce, w telefonie i w sesjach zdalnych nie ma czego policzyć. W ChatGPT plugin jest oznaczony jako „Desktop only”.
- Widzi tylko rozmowy z Claude Code i Codexa. Rozmów na claude.ai i w ChatGPT w przeglądarce nie widać, bo nie zostawiają lokalnych logów.
- Wynik to szacunek oparty na proporcjach cen API, a nie odczyt limitu. Mówi, jaka część zużycia poszła na straty, a nie ile procent limitu tygodniowego.

## Licencja

MIT, zobacz [LICENSE](LICENSE).
