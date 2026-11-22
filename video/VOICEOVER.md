# Lektor do wersji D (`D-Zgrai`, 1:59)

Czasy to początki scen w filmie. Tempo około 2,3 słowa na sekundę, czyli spokojnie; każdy
fragment mieści się w swojej scenie z zapasem na oddech. Napisy na ekranie zostają, lektor
ich nie czyta słowo w słowo, tylko prowadzi.

| Czas | Na ekranie | Tekst lektora |
|---|---|---|
| 0:00 | Czerwony slajd „Problem”, cztery punkty | Reklamy-oszustwa zgłasza się pojedynczo. A oszuści działają kampaniami: zmieniają domeny i twarze, ale zaplecze zostaje. |
| 0:05 | KMP-001: 6 · 5 · 4 · 0 z 5 | Tak wygląda jedna kampania: sześć reklam, pięć domen, czterech reklamodawców. I żadna z tych domen nie jest na liście CERT Polska. |
| 0:10 | TROP, Follow the fake | Dlatego zrobiliśmy TROP. Idziemy po śladach fejka. |
| 0:13 | Strona główna, śpiące boty, przeciągnięty folder | Na start wrzucam cały folder z danych konkursowych: zrzut ekranu, stronę i ruch sieciowy. Żadnego gotowego przykładu. |
| 0:22 | Boty budzą się po kolei | Budzi się sześciu detektywów. Zwiadowca otwiera stronę w piaskownicy. Tropiciel znajduje piksel Facebooka, konto w zestawie strony i landing. Czytelnik czyta treść i osoby. Archiwista porównuje wszystko z bazą. |
| 0:35 | Werdykt KMP-001 · 0.99 | Sędzia: dołącza do kampanii KMP-001, pewność zero dziewięćdziesiąt dziewięć. Następna kampania ma tylko jedną setną. |
| 0:39 | Strona z obrysami | Na przechwyconej stronie widać, gdzie dokładnie są dowody. |
| 0:42 | Graf | Każde powiązanie można kliknąć. Rafał Brzoska pojawia się w pięciu materiałach. Kampania. I operator, który za nią stoi. |
| 0:54 | Ślad: domena, potem osoba | Można też zacząć od samego śladu. Domena dorquesio.click: dwa materiały, ta sama kampania, ten sam zestaw strony. A osoba, Rafał Brzoska: cztery materiały, te same nagłówki. |
| 1:08 | Nowa kampania | Gdy nic nie pasuje, TROP nie zgaduje. Mówi wprost: to nowa kampania. |
| 1:15 | Kampanie, KMP-001, Zgłoszenie | Kampanie są pogrupowane według operatorów. A zamiast sześciu osobnych zgłoszeń przygotowujemy jedno: dla Mety, CERT Polska i w formacie STIX. Wysyła je człowiek, nie my. |
| 1:29 | Śledztwo White Rabbit | Agent White Rabbit startuje od jednej domeny i krok po kroku szuka reszty sieci. |
| 1:38 | „Znaleźliśmy 50 nowych domen” | Pięćdziesiąt nowych domen. Żadnej z nich nie ma jeszcze na liście ostrzeżeń. |
| 1:42 | Wtyczka w przeglądarce | A wtyczka ostrzega tam, gdzie oszustwo naprawdę się pojawia: przy reklamie. |
| 1:49 | Wyniki: 0 · 1.00 · 9/9 · 50 | Zero błędnych powiązań w każdym teście. Dziewięć na dziewięć na danych, których model wcześniej nie widział. |
| 1:55 | Czarna plansza końcowa | TROP. Follow the fake. trop.b.solvro.pl |

## Uwagi

- „0.99” czytaj „zero dziewięćdziesiąt dziewięć” albo „dziewięćdziesiąt dziewięć procent”; na ekranie jest „pewność 0.99”.
- Śledztwo to przyspieszony zapis prawdziwego przebiegu agenta (napis na ekranie to mówi), więc lektor nie mówi „na żywo”.
- Jeśli lektor ma być dłuższy niż scena, wydłuż ją w `src/timeline.ts` (`dur`) i wyrenderuj `pnpm render D-Zgrai` (około 6 minut).
