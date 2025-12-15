import requests
import time
import csv
import random
import concurrent.futures
from bs4 import BeautifulSoup
import os
from datetime import datetime

# Global headers to be used for requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'
}

# Configurações
MAX_THREADS = 10
MOVIES_LIMIT = 10
OUTPUT_FILE = 'movies.csv'


def extract_movie_details(movie_link):
    """Extrai detalhes de um filme individual"""
    time.sleep(random.uniform(0, 0.2))

    try:
        response = requests.get(movie_link, headers=headers, timeout=10)
        response.raise_for_status()
        movie_soup = BeautifulSoup(response.content, 'html.parser')

        if movie_soup is not None:
            title = None
            date = None
            rating = None
            plot_text = None
            genres = None
            duration = None

            # Encontrando a seção específica
            page_section = movie_soup.find('section', attrs={'class': 'ipc-page-section'})

            if page_section is not None:
                # Encontrando todas as divs dentro da seção
                divs = page_section.find_all('div', recursive=False)

                if len(divs) > 1:
                    target_div = divs[1]

                    # Encontrando o título do filme
                    title_tag = target_div.find('h1')
                    if title_tag:
                        title = title_tag.find('span').get_text()

                    # Encontrando a data de lançamento
                    date_tag = target_div.find('a', href=lambda href: href and 'releaseinfo' in href)
                    if date_tag:
                        date = date_tag.get_text().strip()

                    # Encontrando a classificação do filme
                    rating_tag = movie_soup.find('div',
                                                 attrs={'data-testid': 'hero-rating-bar__aggregate-rating__score'})
                    rating = rating_tag.get_text() if rating_tag else 'N/A'

                    # Encontrando a sinopse do filme
                    plot_tag = movie_soup.find('span', attrs={'data-testid': 'plot-xs_to_m'})
                    plot_text = plot_tag.get_text().strip() if plot_tag else 'N/A'

                    # NOVO: Extraindo gêneros
                    genre_tags = movie_soup.find_all('span', attrs={'class': 'ipc-chip__text'})
                    if genre_tags:
                        genres = ', '.join([tag.get_text() for tag in genre_tags[:3]])  # Primeiros 3 gêneros
                    else:
                        genres = 'N/A'

                    # NOVO: Extraindo duração
                    duration_tag = movie_soup.find('li', attrs={'data-testid': 'title-techspec_runtime'})
                    if duration_tag:
                        duration_text = duration_tag.find('div', class_='ipc-metadata-list-item__content-container')
                        duration = duration_text.get_text().strip() if duration_text else 'N/A'
                    else:
                        duration = 'N/A'

                    # Retorna os dados incluindo gêneros e duração
                    if title and date:  # Mais flexível: apenas título e data são obrigatórios
                        return [title, date, rating, genres, duration, plot_text]

    except requests.exceptions.RequestException as e:
        print(f"✗ Erro de conexão em {movie_link}: {e}")
    except Exception as e:
        print(f"✗ Erro ao processar {movie_link}: {e}")

    return None


def extract_movies(soup, limit=None):
    """Extrai lista de filmes da página principal"""
    movies_table = soup.find('div', attrs={'data-testid': 'chart-layout-main-column'}).find('ul')
    movies_table_rows = movies_table.find_all('li')
    movie_links = ['https://imdb.com' + movie.find('a')['href'] for movie in movies_table_rows]

    # Aplica o limite de filmes
    if limit:
        movie_links = movie_links[:limit]
        print(f"🎬 Buscando {len(movie_links)} filmes...\n")
    else:
        print(f"🎬 Buscando todos os {len(movie_links)} filmes encontrados...\n")

    # Processa os filmes com threads
    threads = min(MAX_THREADS, len(movie_links))
    results = []
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = executor.map(extract_movie_details, movie_links)

        for result in futures:
            if result:
                results.append(result)
                print(f"✓ {len(results)}. {result[0]} ({result[1]}) - {result[2]} - {result[3]}")
            else:
                failed += 1

    if failed > 0:
        print(f"\n⚠ {failed} filme(s) não puderam ser processados")

    return results


def save_to_csv(data, filename):
    """Salva os dados em arquivo CSV"""
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        movie_writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # Cabeçalho atualizado com novos campos
        movie_writer.writerow(['Title', 'Date', 'Rating', 'Genres', 'Duration', 'Plot'])
        movie_writer.writerows(data)


def generate_report(movie_data, elapsed_time):
    """Gera um resumo estatístico dos dados coletados"""
    print("\n" + "=" * 60)
    print("📊 RESUMO DA COLETA")
    print("=" * 60)
    print(f"✓ Total de filmes salvos: {len(movie_data)}")
    print(f"✓ Tempo total: {elapsed_time:.2f} segundos")
    print(f"✓ Velocidade média: {elapsed_time / len(movie_data):.2f} seg/filme" if len(movie_data) > 0 else "")
    print(f"✓ Arquivo salvo: {OUTPUT_FILE}")

    # Estatísticas adicionais
    ratings = [float(m[2].split('/')[0]) for m in movie_data if m[2] != 'N/A' and '/' in m[2]]
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        print(f"✓ Rating médio: {avg_rating:.1f}/10")

    # Gêneros mais comuns
    all_genres = []
    for movie in movie_data:
        if movie[3] != 'N/A':
            all_genres.extend([g.strip() for g in movie[3].split(',')])

    if all_genres:
        from collections import Counter
        top_genres = Counter(all_genres).most_common(3)
        print(f"✓ Gêneros mais comuns: {', '.join([f'{g[0]} ({g[1]})' for g in top_genres])}")

    print("=" * 60)


def main():
    print("\n" + "=" * 60)
    print("🎬 IMDb MOVIE SCRAPER")
    print("=" * 60)
    print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"🔧 Configurações: {MOVIES_LIMIT} filmes | {MAX_THREADS} threads")
    print("=" * 60 + "\n")

    start_time = time.time()

    # Remove arquivo anterior se existir
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        print(f"🗑️  Arquivo anterior removido.\n")

    try:
        # IMDB Most Popular Movies
        popular_movies_url = 'https://www.imdb.com/chart/moviemeter/?ref_=nv_mv_mpm'
        print("🌐 Conectando ao IMDb...")
        response = requests.get(popular_movies_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        print("✓ Conectado com sucesso!\n")

        # Extrai os filmes (com limite definido em MOVIES_LIMIT)
        movie_data = extract_movies(soup, limit=MOVIES_LIMIT)

        # Salva os resultados
        if movie_data:
            save_to_csv(movie_data, OUTPUT_FILE)
            end_time = time.time()
            generate_report(movie_data, end_time - start_time)
        else:
            print("\n⚠️  Nenhum filme foi coletado com sucesso.")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Erro ao conectar ao IMDb: {e}")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")


if __name__ == '__main__':
    main()