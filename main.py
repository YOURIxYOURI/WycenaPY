import flet as ft
import json
import os
import urllib.request
from datetime import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos

DB_FILE = "materials_db.json"

def ensure_fonts():
    fonts = {
        "Roboto-Regular.ttf": "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf",
        "Roboto-Bold.ttf": "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
    }
    for filename, url in fonts.items():
        if not os.path.exists(filename):
            print(f"Pobieranie czcionki {filename}...")
            urllib.request.urlretrieve(url, filename)

def load_database():
    if not os.path.exists(DB_FILE):
        sample_db = {
            "Profil aluminiowy 40x40": {"unit": "m", "price": 35.50, "currency": "PLN"},
            "Płyta MDF 18mm": {"unit": "m2", "price": 120.00, "currency": "PLN"},
            "Specjalistyczny Zawias": {"unit": "szt", "price": 2.50, "currency": "EUR"},
            "Klej montażowy": {"unit": "szt", "price": 25.00, "currency": "PLN"}
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(sample_db, f, indent=4, ensure_ascii=False)
        return sample_db

    with open(DB_FILE, 'r', encoding='utf-8') as f:
        db = json.load(f)
        for key, value in db.items():
            if "currency" not in value:
                value["currency"] = "PLN"
        return db


def save_database(db_data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, indent=4, ensure_ascii=False)

def main(page: ft.Page):
    page.title = "Kalkulator Wycen - Generator Ofert"
    page.window.width = 1100
    page.window.height = 950
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 30
    page.scroll = "auto"

    db = load_database()

    skladniki_produktu = []
    wycena_dla_klienta = []
    dropdown_map = {}

    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    message_text = ft.Text(value="", color=ft.Colors.RED_400)

    def pokaz_blad(tekst, color=ft.Colors.RED_400):
        message_text.value = tekst
        message_text.color = color
        page.update()

    def ukryj_blad():
        message_text.value = ""
        page.update()

    material_dropdown = ft.Dropdown(
        label="Wybierz materiał (wpisz lub wybierz z listy)",
        width=450,
        editable=True,
        enable_filter=True,
        enable_search=True
    )

    def odswiez_dropdown():
        dropdown_map.clear()
        for name, data in db.items():
            waluta = data.get("currency", "PLN")
            display_str = f"{name} [{data['unit']}] ({waluta})"
            dropdown_map[display_str] = name

        material_dropdown.options = [ft.dropdown.Option(display_name) for display_name in dropdown_map.keys()]
        try:
            material_dropdown.update()
        except Exception:
            pass

    odswiez_dropdown()

    qty_input = ft.TextField(label="Ilość materiału", value="1", width=120)
    margin_input = ft.TextField(label="Marża (%)", value="30", width=100)

    suma_skladnikow_text = ft.Text("Koszt produkcji: 0.00 zł  |  Sugerowana cena (z marżą): 0.00 zł",
                                   weight=ft.FontWeight.BOLD)

    tabela_skladnikow = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Materiał")),
            ft.DataColumn(ft.Text("Ilość")),
            ft.DataColumn(ft.Text("Cena jedn. (zakup)")),
            ft.DataColumn(ft.Text("Suma (zakup)")),
            ft.DataColumn(ft.Text("Suma (z marżą)")),
            ft.DataColumn(ft.Text("")),
        ],
        rows=[]
    )

    def odswiez_tabele_skladnikow():
        tabela_skladnikow.rows.clear()
        total_base = 0
        total_margin = 0
        for i, item in enumerate(skladniki_produktu):
            tabela_skladnikow.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item["name"])),
                        ft.DataCell(ft.Text(f'{item["quantity"]} {item["unit"]}')),
                        ft.DataCell(ft.Text(f'{item["base_price"]:.2f} zł')),
                        ft.DataCell(ft.Text(f'{item["base_total"]:.2f} zł')),
                        ft.DataCell(ft.Text(f'{item["margin_total"]:.2f} zł')),
                        ft.DataCell(ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_400,
                                                  on_click=lambda e, idx=i: usun_ze_skladnikow(idx))),
                    ]
                )
            )
            total_base += item["base_total"]
            total_margin += item["margin_total"]
        suma_skladnikow_text.value = f"Koszt produkcji: {total_base:.2f} zł  |  Sugerowana cena (z marżą): {total_margin:.2f} zł"
        page.update()

    def przelicz_kurs(e):
        try:
            nowy_kurs = float(kurs_euro_input.value.replace(',', '.'))

            for item in skladniki_produktu:
                if item.get("currency") == "EUR":
                    item["base_price"] = item["raw_price"] * nowy_kurs
                    item["price_with_margin"] = item["base_price"] * (1 + item["margin"] / 100)
                    item["base_total"] = item["base_price"] * item["quantity"]
                    item["margin_total"] = item["price_with_margin"] * item["quantity"]

            for prod in wycena_dla_klienta:
                nowa_cena_jednostkowa = 0
                for sk in prod["skladniki"]:
                    if sk.get("currency") == "EUR":
                        sk["base_price"] = sk["raw_price"] * nowy_kurs
                        sk["price_with_margin"] = sk["base_price"] * (1 + sk["margin"] / 100)
                        sk["base_total"] = sk["base_price"] * sk["quantity"]
                        sk["margin_total"] = sk["price_with_margin"] * sk["quantity"]
                    nowa_cena_jednostkowa += sk["margin_total"]

                prod["cena_jedn"] = nowa_cena_jednostkowa
                prod["suma"] = nowa_cena_jednostkowa * prod["ilosc"]

            odswiez_tabele_skladnikow()
            odswiez_tabele_wyceny()
        except ValueError:
            pass


    kurs_euro_input = ft.TextField(label="Kurs EUR (zł)", value="4.30", width=120, on_change=przelicz_kurs)

    klient_input = ft.TextField(label="Odbiorca / Klient", value="", width=250)

    def usun_ze_skladnikow(index):
        if 0 <= index < len(skladniki_produktu):
            del skladniki_produktu[index]
            odswiez_tabele_skladnikow()

    def dodaj_material(e):
        selected_display = material_dropdown.value
        if not selected_display:
            pokaz_blad("Wybierz materiał z listy!")
            return

        if selected_display not in dropdown_map:
            pokaz_blad("Taki materiał nie istnieje w bazie! Wybierz pozycję z podpowiedzi.")
            return

        try:
            qty = float(qty_input.value.replace(',', '.'))
            margin = float(margin_input.value.replace(',', '.'))
            kurs_eur = float(kurs_euro_input.value.replace(',', '.'))

            real_name = dropdown_map[selected_display]
            raw_price = db[real_name]["price"]
            currency = db[real_name].get("currency", "PLN")

            if currency == "EUR":
                base_price = raw_price * kurs_eur
            else:
                base_price = raw_price

            price_with_margin = base_price * (1 + margin / 100)

            skladniki_produktu.append({
                "name": real_name,
                "quantity": qty,
                "unit": db[real_name]["unit"],
                "currency": currency,
                "raw_price": raw_price,
                "margin": margin,
                "base_price": base_price,
                "price_with_margin": price_with_margin,
                "base_total": base_price * qty,
                "margin_total": price_with_margin * qty
            })
            ukryj_blad()
            odswiez_tabele_skladnikow()
        except ValueError:
            pokaz_blad("Wpisz poprawne liczby w polach Ilość/Marża/Kurs EUR!")

    nazwa_produktu_input = ft.TextField(label="Nazwa gotowego produktu (np. Skrzynia A)", width=400)
    ilosc_produktu_input = ft.TextField(label="Ilość sztuk", value="1", width=100)
    suma_wyceny_text = ft.Text("Suma całkowita dla klienta: 0.00 zł", size=24, weight=ft.FontWeight.BOLD,
                               color=ft.Colors.GREEN_400)

    tabela_wyceny = ft.DataTable(
        data_row_max_height=float("inf"),
        columns=[
            ft.DataColumn(ft.Text("Gotowy Produkt (dla klienta)")),
            ft.DataColumn(ft.Text("Ilość")),
            ft.DataColumn(ft.Text("Cena jedn.")),
            ft.DataColumn(ft.Text("Suma")),
            ft.DataColumn(ft.Text("")),
        ],
        rows=[]
    )

    def usun_z_wyceny(index):
        if 0 <= index < len(wycena_dla_klienta):
            del wycena_dla_klienta[index]
            odswiez_tabele_wyceny()

    def odswiez_tabele_wyceny():
        tabela_wyceny.rows.clear()
        suma_calkowita = 0
        for i, prod in enumerate(wycena_dla_klienta):
            zawartosc_komorki = ft.Column(
                [
                    ft.Text(prod["nazwa"], weight=ft.FontWeight.BOLD, size=14),
                    ft.Text(prod["szczegoly"], size=11, color=ft.Colors.WHITE54, italic=True)
                ],
                spacing=2, alignment=ft.MainAxisAlignment.CENTER
            )
            tabela_wyceny.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(zawartosc_komorki),
                        ft.DataCell(ft.Text(f'{prod["ilosc"]} szt')),
                        ft.DataCell(ft.Text(f'{prod["cena_jedn"]:.2f} zł')),
                        ft.DataCell(ft.Text(f'{prod["suma"]:.2f} zł')),
                        ft.DataCell(ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_400,
                                                  on_click=lambda e, idx=i: usun_z_wyceny(idx))),
                    ]
                )
            )
            suma_calkowita += prod["suma"]
        suma_wyceny_text.value = f"Suma całkowita dla klienta: {suma_calkowita:.2f} zł"
        page.update()

    def zatwierdz_produkt(e):
        if not skladniki_produktu:
            pokaz_blad("Najpierw dodaj materiały, żeby stworzyć produkt!")
            return
        nazwa = nazwa_produktu_input.value.strip()
        if not nazwa:
            pokaz_blad("Podaj nazwę dla gotowego produktu!")
            return
        try:
            ilosc_sztuk = float(ilosc_produktu_input.value.replace(',', '.'))
            cena_jednostkowa_produktu = sum(item["margin_total"] for item in skladniki_produktu)
            lista_opisowa = [f"{item['name']} ({item['quantity']} {item['unit']})" for item in skladniki_produktu]
            tekst_szczegolowy = "Zawiera: " + ", ".join(lista_opisowa)

            kopia_skladnikow = [dict(item) for item in skladniki_produktu]

            wycena_dla_klienta.append({
                "nazwa": nazwa,
                "szczegoly": tekst_szczegolowy,
                "ilosc": ilosc_sztuk,
                "cena_jedn": cena_jednostkowa_produktu,
                "suma": cena_jednostkowa_produktu * ilosc_sztuk,
                "skladniki": kopia_skladnikow
            })
            skladniki_produktu.clear()
            nazwa_produktu_input.value = ""
            ilosc_produktu_input.value = "1"
            ukryj_blad()
            odswiez_tabele_skladnikow()
            odswiez_tabele_wyceny()
        except ValueError:
            pokaz_blad("Wpisz poprawną ilość gotowego produktu!")

    async def zapytaj_o_sciezke(e):
        if not wycena_dla_klienta:
            pokaz_blad("Wycena końcowa jest pusta! Zbuduj i zatwierdź produkt.")
            return
        sciezka_zapisu = await file_picker.save_file(
            dialog_title="Zapisz wycenę jako...",
            file_name="wycena_projektu.pdf",
            allowed_extensions=["pdf"]
        )
        if sciezka_zapisu:
            if not sciezka_zapisu.lower().endswith(".pdf"):
                sciezka_zapisu += ".pdf"
            generuj_prawdziwy_pdf(sciezka_zapisu)

    def generuj_prawdziwy_pdf(sciezka_zapisu):
        ensure_fonts()
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("Roboto", style="", fname="Roboto-Regular.ttf")
        pdf.add_font("Roboto", style="B", fname="Roboto-Bold.ttf")
        logo_path = "logo.png"

        if os.path.exists(logo_path):
            with pdf.local_context(fill_opacity=0.1):
                with pdf.rotation(angle=45, x=105, y=148):
                    pdf.image(logo_path, x=45, y=110, w=150)

        pdf.set_font("Roboto", 'B', 22)
        pdf.cell(0, 10, "OFERTA CENOWA", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

        dzisiejsza_data = datetime.now().strftime("%d.%m.%Y")
        pdf.set_font("Roboto", '', 11)
        pdf.cell(0, 6, f"Data sporządzenia: {dzisiejsza_data}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

        dla_kogo = klient_input.value.strip()
        if not dla_kogo:
            dla_kogo = "Klient detaliczny"

        pdf.set_font("Roboto", 'B', 12)
        pdf.cell(0, 8, f"Przygotowano dla: {dla_kogo}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

        if os.path.exists(logo_path):
            pdf.image(logo_path, x=150, y=10, w=50)

        pdf.ln(5)

        y_linii = pdf.get_y()
        pdf.line(10, y_linii, 200, y_linii)
        pdf.ln(10)

        h = 8
        pdf.set_font("Roboto", 'B', 9)
        pdf.set_fill_color(230, 230, 230)

        pdf.cell(80, h, "Nazwa Produktu", border=1, fill=True)
        pdf.cell(15, h, "Ilość", border=1, align='C', fill=True)
        pdf.cell(30, h, "Cena Netto", border=1, align='C', fill=True)
        pdf.cell(30, h, "Wartość Netto", border=1, align='C', fill=True)
        pdf.cell(35, h, "Wartość Brutto", border=1, align='C', fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Roboto", '', 9)
        total_netto = 0
        total_brutto = 0

        for prod in wycena_dla_klienta:
            suma_netto = prod["suma"]
            suma_brutto = suma_netto * 1.23

            pdf.cell(80, h, prod["nazwa"], border=1)
            pdf.cell(15, h, f'{prod["ilosc"]} szt', border=1, align='C')
            pdf.cell(30, h, f'{prod["cena_jedn"]:.2f} zł', border=1, align='C')
            pdf.cell(30, h, f'{suma_netto:.2f} zł', border=1, align='C')
            pdf.cell(35, h, f'{suma_brutto:.2f} zł', border=1, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            total_netto += suma_netto
            total_brutto += suma_brutto

        pdf.ln(5)
        kwota_vat = total_brutto - total_netto

        pdf.set_font("Roboto", '', 11)
        pdf.cell(150, 7, "Suma całkowita Netto:", align='R')
        pdf.cell(40, 7, f"{total_netto:.2f} zł", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.cell(150, 7, "Kwota VAT (23%):", align='R')
        pdf.cell(40, 7, f"{kwota_vat:.2f} zł", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Roboto", 'B', 13)
        pdf.cell(150, 10, "Suma całkowita BRUTTO do zapłaty:", align='R')
        pdf.cell(40, 10, f"{total_brutto:.2f} zł", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(15)
        pdf.set_font("Roboto", '', 8)
        pdf.set_text_color(100, 100, 100)

        stopka_tekst = (
            "Termin ważności oferty: 7 dni. Niniejsza oferta ma charakter informacyjny. Wiążąca umowa sprzedaży "
            "zostaje zawarta w momencie opłacenia faktury Pro Forma, która określa ostateczną specyfikację "
            "i warunki cenowe. Zastrzegamy sobie prawo do aktualizacji ceny w przypadku zmiany specyfikacji "
            "przez Zamawiającego (np. zmiana wymiarów urządzenia lub zmiana komponentów na życzenie)."
        )

        pdf.multi_cell(0, 5, stopka_tekst, align='C')

        pdf.output(sciezka_zapisu)
        pokaz_blad("Zapisano pomyślnie na dysku!", ft.Colors.GREEN_400)

    kalkulator_content = ft.Column([
        ft.Text("KROK 1: Skompletuj produkt z materiałów", size=20, weight=ft.FontWeight.BOLD,
                color=ft.Colors.BLUE_200),
        ft.Row([material_dropdown, qty_input, margin_input,
                ft.Button("Dodaj materiał", on_click=dodaj_material, bgcolor=ft.Colors.BLUE_700,
                          color=ft.Colors.WHITE)]),
        tabela_skladnikow,
        suma_skladnikow_text,
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Row([nazwa_produktu_input, ilosc_produktu_input,
                ft.Button("Zatwierdź i dodaj do wyceny", on_click=zatwierdz_produkt, bgcolor=ft.Colors.GREEN_600,
                          color=ft.Colors.WHITE)]),
        ft.Divider(height=30, color=ft.Colors.WHITE24),
        ft.Text("KROK 2: Gotowa wycena dla klienta", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_200),
        tabela_wyceny,
        suma_wyceny_text,

        ft.Row([
            kurs_euro_input,
            klient_input,
            ft.Button("Generuj PDF dla klienta", on_click=zapytaj_o_sciezke, bgcolor=ft.Colors.AMBER_700,
                      color=ft.Colors.WHITE)
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    ], scroll="adaptive")


    db_nazwa_input = ft.TextField(label="Nazwa nowego materiału", width=250)
    db_jednostka_input = ft.TextField(label="Jednostka", width=150)
    db_cena_input = ft.TextField(label="Cena", width=100)
    db_waluta_dropdown = ft.Dropdown(label="Waluta", options=[ft.dropdown.Option("PLN"), ft.dropdown.Option("EUR")],
                                     value="PLN", width=100)

    tabela_bazy = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Nazwa materiału")),
            ft.DataColumn(ft.Text("Jednostka")),
            ft.DataColumn(ft.Text("Cena bazowa")),
            ft.DataColumn(ft.Text("Akcja")),
        ],
        rows=[]
    )

    def odswiez_tabele_bazy():
        tabela_bazy.rows.clear()
        for name, data in db.items():
            waluta = data.get("currency", "PLN")
            tabela_bazy.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(name)),
                        ft.DataCell(ft.Text(data["unit"])),
                        ft.DataCell(ft.Text(f'{data["price"]:.2f} {waluta}')),
                        ft.DataCell(ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_400,
                                                  on_click=lambda e, n=name: usun_z_bazy(n))),
                    ]
                )
            )
        page.update()

    def usun_z_bazy(nazwa_materialu):
        if nazwa_materialu in db:
            del db[nazwa_materialu]
            save_database(db)
            odswiez_tabele_bazy()
            odswiez_dropdown()
            pokaz_blad(f"Usunięto materiał: {nazwa_materialu}", ft.Colors.ORANGE_400)

    def dodaj_do_bazy(e):
        nazwa = db_nazwa_input.value.strip()
        jednostka = db_jednostka_input.value.strip()
        waluta = db_waluta_dropdown.value

        if not nazwa or not jednostka:
            pokaz_blad("Wypełnij nazwę i jednostkę!")
            return

        if nazwa in db:
            pokaz_blad("Materiał o takiej nazwie już istnieje!")
            return

        try:
            cena = float(db_cena_input.value.replace(',', '.'))

            db[nazwa] = {"unit": jednostka, "price": cena, "currency": waluta}
            save_database(db)

            db_nazwa_input.value = ""
            db_jednostka_input.value = ""
            db_cena_input.value = ""

            odswiez_tabele_bazy()
            odswiez_dropdown()
            pokaz_blad("Dodano pomyślnie do bazy!", ft.Colors.GREEN_400)

        except ValueError:
            pokaz_blad("Wpisz poprawną cenę (liczbę)!")

    odswiez_tabele_bazy()

    baza_content = ft.Column([
        ft.Text("Dodaj nowy materiał do bazy", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([
            db_nazwa_input,
            db_jednostka_input,
            db_cena_input,
            db_waluta_dropdown,
            ft.Button("Zapisz w bazie", on_click=dodaj_do_bazy, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
        ]),
        ft.Divider(height=20),
        ft.Text("Aktualnie zapisane materiały", size=20, weight=ft.FontWeight.BOLD),
        tabela_bazy
    ], scroll="adaptive")

    kalkulator_container = ft.Container(content=kalkulator_content, visible=True)
    baza_container = ft.Container(content=baza_content, visible=False)

    def pokaz_kalkulator(e):
        kalkulator_container.visible = True
        baza_container.visible = False
        btn_kalkulator.bgcolor = ft.Colors.BLUE_700
        btn_baza.bgcolor = ft.Colors.GREY_800
        page.update()

    def pokaz_baze(e):
        kalkulator_container.visible = False
        baza_container.visible = True
        btn_kalkulator.bgcolor = ft.Colors.GREY_800
        btn_baza.bgcolor = ft.Colors.BLUE_700
        page.update()

    btn_kalkulator = ft.Button("1. Kalkulator Ofert", icon=ft.Icons.CALCULATE, on_click=pokaz_kalkulator,
                               bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE)
    btn_baza = ft.Button("2. Baza Materiałów", icon=ft.Icons.STORAGE, on_click=pokaz_baze, bgcolor=ft.Colors.GREY_800,
                         color=ft.Colors.WHITE)

    zakladki_menu = ft.Row([btn_kalkulator, btn_baza], spacing=20)

    page.add(
        ft.Text("System Zarządzania Wycenami", size=28, weight=ft.FontWeight.BOLD),
        message_text,
        zakladki_menu,
        ft.Divider(height=10),
        kalkulator_container,
        baza_container
    )


ft.run(main)