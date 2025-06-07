import os
from flask import Flask, render_template, request
from data_processor import process_files

# Inicjalizacja aplikacji Flask
app = Flask(__name__)

# Folder do przechowywania wgranych plików
UPLOAD_FOLDER = 'uploads'
# Tworzenie folderu 'uploads' jeśli nie istnieje
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Konfiguracja folderu dla wgranych plików
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Obsługuje stronę główną aplikacji, w której użytkownik może wgrać pliki CSV.
    Metody GET: Wyświetla formularz do wgrania plików.
    Metody POST: Przetwarza wgrane pliki CSV i wyświetla wyniki porównania.
    """
    if request.method == 'POST':
        # Pobieranie listy wgranych plików
        files = request.files.getlist('files')

        # Pobieranie nazw kolumn z formularza, z domyślnymi wartościami
        code_col = request.form.get('code_column', 'code')
        name_col = request.form.get('name_column', 'name')
        price_col = request.form.get('price_column', 'price')

        saved_files = []
        # Iteracja przez wgrane pliki
        for file in files:
            # Sprawdzanie, czy plik istnieje i czy ma rozszerzenie .csv
            if file and file.filename and file.filename.endswith('.csv'):
                # Tworzenie pełnej ścieżki do zapisu pliku
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                # Zapisywanie pliku
                file.save(file_path)
                saved_files.append(file_path)

        # Sprawdzanie, czy wgrano co najmniej dwa pliki CSV
        if len(saved_files) < 2:
            return render_template('index.html', error="Proszę wgrać co najmniej dwa pliki CSV.")

        try:
            # Tworzenie słownika mapowania kolumn
            column_mapping = {code_col: 'code', name_col: 'name', price_col: 'price'}
            # Przetwarzanie plików za pomocą funkcji z data_processor.py
            comparison_data, wholesalers = process_files(saved_files, column_mapping)
            # Renderowanie szablonu z wynikami
            return render_template('results.html', data=comparison_data, wholesalers=wholesalers)
        except ValueError as e:
            # Obsługa błędów związanych z brakującymi kolumnami lub formatem plików
            return render_template('index.html', error=f"Błąd danych: {str(e)}")
        except Exception as e:
            # Ogólna obsługa innych błędów przetwarzania
            return render_template('index.html', error=f"Wystąpił nieoczekiwany błąd przetwarzania: {str(e)}")
    
    # Renderowanie początkowego formularza dla metody GET
    return render_template('index.html')

if __name__ == '__main__':
    # Uruchamianie aplikacji w trybie debugowania (tylko do rozwoju)
    app.run(debug=True)
