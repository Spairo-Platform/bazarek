# Spairo Trener

Skille, które patrzą, jak pracujesz z AI, i podpowiadają, co zmienić. Działają w **Claude Code** i w **Codexie**.

## Skille

### `gdzie-tracisz-limit`

Pokazuje, jaka część Twojego zużycia idzie na dwie rzeczy, których da się uniknąć:

- **długa historia rozmowy**: przy każdej wiadomości AI czyta od nowa całą rozmowę, więc w długim wątku każda wiadomość kosztuje więcej;
- **wznowienia po przerwie**: po dłuższej przerwie albo zmianie modelu cała rozmowa wczytuje się od nowa, kilkanaście razy drożej niż zwykle.

Dostajesz werdykt, top rozmowy, w których uciekło najwięcej, i trend z ostatnich 4 tygodni. W aplikacji Claude wynik jest interaktywny: suwakiem ustawiasz, jak długie rozmowy chcesz prowadzić, i od razu widzisz, ile byś zaoszczędził(a).

Zapytaj po prostu: „Gdzie tracę limit?” albo „Czemu tak szybko kończy mi się limit?”.

## Instalacja

**Claude Code**

```bash
claude plugin marketplace add Spairo-Platform/spairo-trener
```

```bash
claude plugin install spairo-trener@spairo-trener
```

Skill wywołasz też wprost: `/spairo-trener:gdzie-tracisz-limit`.

**Codex**

```bash
codex plugin marketplace add Spairo-Platform/spairo-trener
```

```bash
codex plugin add spairo-trener@spairo-trener
```

Możesz też zainstalować plugin **Spairo Trener** z listy pluginów w aplikacji Codex.

## Prywatność

Skrypt czyta tylko lokalne logi na Twoim komputerze (`~/.claude/projects` albo `~/.codex/sessions`) i niczego nie wysyła. Do działania wystarczy Python 3, bez dodatkowych bibliotek.

## Ograniczenia

- Widzi tylko rozmowy z Claude Code i Codexa. Rozmów na claude.ai i w ChatGPT w przeglądarce nie widać, bo nie zostawiają lokalnych logów.
- Wynik to szacunek oparty na proporcjach cen API, a nie odczyt limitu. Mówi, jaka część zużycia poszła na straty, a nie ile procent limitu tygodniowego.

## Licencja

MIT, zobacz [LICENSE](LICENSE).
