import os
import pandas as pd
from fuzzywuzzy import fuzz
from collections import namedtuple

# Definicja nazwanej krotki do przechowywania danych porównawczych
ComparisonRow = namedtuple('ComparisonRow', ['product', 'prices', 'difference', 'best_price'])

def process_files(file_paths, column_mapping):
    """
    Przetwarza listę ścieżek do plików CSV, porównując ceny produktów.

    Args:
        file_paths (list): Lista ścieżek do plików CSV.
        column_mapping (dict): Słownik mapujący nazwy kolumn z plików CSV
                               na standardowe nazwy ('code', 'name', 'price').

    Returns:
        tuple: Krotka zawierająca listę obiektów ComparisonRow oraz listę nazw hurtowni.

    Raises:
        ValueError: Jeśli pliki CSV nie zawierają wymaganych kolumn
                    lub nie można ich poprawnie wczytać.
    """
    dfs = []
    wholesalers = []
    
    # Odwrócone mapowanie do sprawdzenia obecności kolumn przed zmianą nazw
    # Klucze z column_mapping to oryginalne nazwy kolumn, wartości to standardowe nazwy.
    # Potrzebujemy oryginalnych nazw, aby sprawdzić, czy są w pliku.
    required_original_cols = set(column_mapping.keys())

    # Wczytaj wszystkie pliki CSV z obsługą różnych kodowań
    for file_path in file_paths:
        file_name = os.path.basename(file_path)
        df = None
        try:
            # Spróbuj wczytać z kodowaniem UTF-8
            df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip', sep=None, engine='python')
        except UnicodeDecodeError:
            try:
                # Jeśli UTF-8 nie działa, spróbuj Windows-1250
                df = pd.read_csv(file_path, encoding='windows-1250', on_bad_lines='skip', sep=None, engine='python')
            except Exception as e:
                # Jeśli żadne kodowanie nie działa, zgłoś błąd
                raise ValueError(f"Nie udało się wczytać pliku {file_name} z powodu błędu kodowania lub formatu: {e}")
        
        if df is None:
            raise ValueError(f"Nie udało się wczytać pliku {file_name}. Sprawdź format pliku.")

        # Sprawdzenie, czy wszystkie wymagane oryginalne kolumny są obecne w wczytanym DataFrame
        if not required_original_cols.issubset(df.columns):
            missing_cols = required_original_cols - set(df.columns)
            raise ValueError(f"Plik {file_name} nie zawiera wymaganych kolumn: {', '.join(missing_cols)}. Upewnij się, że podane nazwy kolumn są poprawne.")
        
        # Zmiana nazw kolumn w DataFrame na standardowe ('code', 'name', 'price')
        # Używamy tylko tych kolumn, które są w mapowaniu, aby uniknąć błędów
        # dla kolumn, które nie są istotne dla przetwarzania.
        df = df.rename(columns=column_mapping)
        
        # Sprawdzenie, czy po zmianie nazw kolumny 'code', 'name', 'price' istnieją
        if not {'code', 'name', 'price'}.issubset(df.columns):
             raise ValueError(f"Wystąpił problem z mapowaniem kolumn w pliku {file_name}. "
                             f"Upewnij się, że każda z kolumn (kod, nazwa, cena) została poprawnie zmapowana.")

        # Konwersja kolumny 'code' na string, aby zapewnić spójność typów
        df['code'] = df['code'].astype(str)
        # Konwersja kolumny 'price' na typ numeryczny, obsługa błędów za pomocą coerce (NaN dla niepoprawnych wartości)
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        
        dfs.append(df)
        wholesalers.append(file_name) # Dodanie nazwy pliku jako nazwy hurtowni
    
    # Zbierz wszystkie unikalne kody produktów ze wszystkich wczytanych DataFrame'ów
    products = set()
    for df in dfs:
        products.update(df['code'].tolist())
    
    comparison_data = []
    # Iteruj przez każdy unikalny kod produktu
    for product_code in products:
        # Inicjalizacja danych dla bieżącego produktu
        product_data = {'code': product_code, 'name': '', 'prices': [], 'difference': None, 'best_price': None}
        
        # Zbierz dane (głównie ceny) dla każdego produktu z każdego DataFrame (hurtowni)
        for df in dfs:
            # Spróbuj dopasować produkt po kodzie
            product_row = df[df['code'] == product_code]
            if not product_row.empty:
                # Jeśli znaleziono po kodzie, pobierz cenę i nazwę
                price = product_row['price'].iloc[0]
                # Ustaw nazwę produktu, jeśli jeszcze nie została ustawiona
                if not product_data['name']:
                    product_data['name'] = product_row['name'].iloc[0]
                product_data['prices'].append(price)
            else:
                # Jeśli nie znaleziono po kodzie, spróbuj dopasować po nazwie (fuzzy matching)
                matched = False
                # Pętla przez wiersze w bieżącym DataFrame
                for _, row in df.iterrows():
                    # Jeśli nazwa produktu w product_data jest już znana
                    if product_data['name'] and pd.notna(product_data['name']) and pd.notna(row['name']) and \
                       fuzz.ratio(product_data['name'].lower(), str(row['name']).lower()) > 80: # Próg dopasowania 80%
                        # Jeśli nazwa pasuje, dodaj cenę i ustaw flagę matched
                        product_data['prices'].append(row['price'])
                        matched = True
                        break # Przerwij pętlę po znalezieniu pierwszego dopasowania
                if not matched:
                    # Jeśli nie znaleziono dopasowania ani po kodzie, ani po nazwie, dodaj None
                    product_data['prices'].append(None)
        
        # Oblicz różnicę i najlepszą cenę na podstawie zebranych cen
        # Filtrujemy None i NaN (Not a Number) z listy cen
        valid_prices = [p for p in product_data['prices'] if pd.notna(p)]

        if len(valid_prices) > 1:
            product_data['difference'] = max(valid_prices) - min(valid_prices)
            product_data['best_price'] = min(valid_prices)
        elif valid_prices:
            # Jeśli jest tylko jedna ważna cena, ustaw ją jako najlepszą
            product_data['best_price'] = valid_prices[0]
        else:
            # Jeśli nie ma żadnych ważnych cen, ustaw None
            product_data['best_price'] = None
            product_data['difference'] = None # Upewnij się, że różnica też jest None

        # Upewnij się, że nazwa produktu jest ustawiona (jeśli nie została znaleziona wcześniej, użyj kodu)
        if not product_data['name'] and product_code:
            product_data['name'] = f"Produkt {product_code}" # Fallback, jeśli nazwa nie została znaleziona
        elif not product_data['name']:
            product_data['name'] = "Nieznany produkt" # Całkowity fallback

        # Dodanie wiersza porównawczego do listy wyników
        comparison_data.append(ComparisonRow(
            product=product_data['name'],
            prices=product_data['prices'],
            difference=product_data['difference'],
            best_price=product_data['best_price']
        ))
    
    return comparison_data, wholesalers
