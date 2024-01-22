import math
import os
import sys

import pygame
import requests

LAT_STEP = 0.008  # Шаги при движении карты по широте и долготе
LON_STEP = 0.02
coord_to_geo_x = 0.0000428  # Пропорции пиксельных и географических координат.
coord_to_geo_y = 0.0000428


def lonlat_distance(a, b):
    degree_to_meters_factor = 111 * 1000  # 111 километров в метрах
    a_lon, a_lat = a
    b_lon, b_lat = b

    # Берем среднюю по широте точку и считаем коэффициент для нее.
    radians_lattitude = math.radians((a_lat + b_lat) / 2.)
    lat_lon_factor = math.cos(radians_lattitude)

    # Вычисляем смещения в метрах по вертикали и горизонтали.
    dx = abs(a_lon - b_lon) * degree_to_meters_factor * lat_lon_factor
    dy = abs(a_lat - b_lat) * degree_to_meters_factor

    # Вычисляем расстояние между точками.
    distance = math.sqrt(dx * dx + dy * dy)

    return distance


# Найти объект по координатам.
def reverse_geocode(ll):
    geocoder_request_template = "http://geocode-maps.yandex.ru/1.x/?apikey=XXXXXXXXXXXXXX&geocode={ll}&format=json"

    # Выполняем запрос к геокодеру, анализируем ответ.
    geocoder_request = geocoder_request_template.format(**locals())
    response = requests.get(geocoder_request)

    if not response:
        raise RuntimeError(
            """Ошибка выполнения запроса:
            {request}
            Http статус: {status} ({reason})""".format(
                request=geocoder_request, status=response.status_code, reason=response.reason))

    # Преобразуем ответ в json-объект
    json_response = response.json()

    # Получаем первый топоним из ответа геокодера.
    features = json_response["response"]["GeoObjectCollection"]["featureMember"]
    return features[0]["GeoObject"] if features else None


def find_business(ll):
    search_api_server = "https://search-maps.yandex.ru/v1/"
    api_key = "XXXXXXXXXXXX"  # вставить api_key
    search_params = {
        "apikey": api_key,
        "lang": "ru_RU",
        "ll": ll,
        "spn": "0.001,0.001",
        "type": "biz",
        "text": 'Москва'
    }

    response = requests.get(search_api_server, params=search_params)
    if not response:
        print(response.text)
        raise RuntimeError(
            """Ошибка выполнения запроса:
            {request}
            Http статус: {status} ({reason})""".format(
                request=search_api_server, status=response.status_code, reason=response.reason))

    # Преобразуем ответ в json-объект
    json_response = response.json()

    # Получаем первую найденную организацию.
    organizations = json_response["features"]
    return organizations[0] if organizations else None


def ll(x, y):
    return "{0},{1}".format(x, y)


# Структура для хранения результатов поиска:
# координаты объекта, его название и почтовый индекс, если есть.
class SearchResult(object):
    def __init__(self, point, address, postal_code=None):
        self.point = point
        self.address = address
        self.postal_code = postal_code

    def __str__(self):
        return f'{self.address}, {self.postal_code}'


class MapParams:
    # Параметры по умолчанию.
    def __init__(self):
        self.lat = XXXXX  # Координаты центра карты на старте.
        self.lon = XXXXX
        self.zoom = 15  # Масштаб карты на старте.
        self.type = "map"  # Тип карты на старте.

        self.search_result = None  # Найденный объект для отображения на карте.
        # self.use_postal_code = False

    # Преобразование координат в параметр ll
    def ll(self):
        return "{0},{1}".format(self.lon, self.lat)

    # Обновление параметров карты по нажатой клавише.
    def update(self, event):
        print(event.key)
        if event.key == pygame.K_UP and self.zoom < 19:  # PG_UP
            self.zoom += 1
        elif event.key == pygame.K_DOWN and self.zoom > 2:  # PG_DOWN
            self.zoom -= 1
        elif event.key == pygame.K_a:  # LEFT_ARROW
            self.lon -= LON_STEP * math.pow(2, 13 - self.zoom)
        elif event.key == pygame.K_d:  # RIGHT_ARROW
            self.lon += LON_STEP * math.pow(2, 13 - self.zoom)
        elif event.key == pygame.K_w and self.lat < 85:  # UP_ARROW
            self.lat += LAT_STEP * math.pow(2, 13 - self.zoom)
        elif event.key == pygame.K_s and self.lat > -85:  # DOWN_ARROW
            self.lat -= LAT_STEP * math.pow(2, 13 - self.zoom)
        elif event.key == 49:  # 1
            self.type = "map"
        elif event.key == 50:  # 2
            self.type = "sat"
        elif event.key == 51:  # 3
            self.type = "sat,skl"
        # elif event.key == 127:  # DELETE
        #     self.search_result = None
        # elif event.key == 277:  # INSERT
        #     self.use_postal_code = not self.use_postal_code
        #
        if self.lon > 180: self.lon -= 360
        if self.lon < -180: self.lon += 360

    # Преобразование экранных координат в географические.
    def screen_to_geo(self, pos):
        dy = 225 - pos[1]
        dx = pos[0] - 300
        lx = self.lon + dx * coord_to_geo_x * math.pow(2, 15 - self.zoom)
        ly = self.lat + dy * coord_to_geo_y * math.cos(math.radians(self.lat)) * math.pow(2,
                                                                                          15 - self.zoom)
        return lx, ly

    def add_reverse_toponym_search(self, pos):
        point = self.screen_to_geo(pos)
        toponym = reverse_geocode(ll(point[0], point[1]))
        self.search_result = SearchResult(
            point,
            toponym["metaDataProperty"]["GeocoderMetaData"]["text"] if toponym else None,
            toponym["metaDataProperty"]["GeocoderMetaData"]["Address"].get(
                "postal_code") if toponym else None)

    # Добавить результат поиска организации на карту.
    def add_reverse_org_search(self, pos):
        self.search_result = None
        point = self.screen_to_geo(pos)
        org = find_business(ll(point[0], point[1]))
        if not org:
            return
        org_point = org["geometry"]["coordinates"]
        org_lon = float(org_point[0])
        org_lat = float(org_point[1])

        # Проверяем, что найденный объект не дальше 50м от места клика.
        if lonlat_distance((org_lon, org_lat), point) <= 50:
            print(org)
            self.search_result = SearchResult(point, org["properties"]["CompanyMetaData"]["name"])


# Создание карты с соответствующими параметрами.
def load_map(mp: MapParams):
    map_request = "http://static-maps.yandex.ru/1.x/"

    params = {
        'll': mp.ll(),
        'z': mp.zoom,
        'l': mp.type
    }

    if mp.search_result:
        params['pt'] = f'{mp.search_result.point[0]},{mp.search_result.point[1]},pm2grm'

    response = requests.get(map_request, params=params)
    if not response:
        print("Ошибка выполнения запроса:")
        print(map_request)
        print("Http статус:", response.status_code, "(", response.reason, ")")
        sys.exit(1)

    # Запишем полученное изображение в файл.
    map_file = "map.png"
    try:
        with open(map_file, "wb") as file:
            file.write(response.content)
    except IOError as ex:
        print("Ошибка записи временного файла:", ex)
        sys.exit(2)

    return map_file

# Создание холста с текстом.
def render_text(text):
    font = pygame.font.Font(None, 30)
    return font.render(text, 1, (100, 0, 100))


def main():
    pygame.init()
    screen = pygame.display.set_mode((600, 450))
    mp = MapParams()
    running = True
    while running:
        event = pygame.event.wait()
        if event.type == pygame.QUIT:
            break
        elif event.type == pygame.KEYUP:
            mp.update(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # LEFT_MOUSE_BUTTON
                mp.add_reverse_toponym_search(event.pos)
            elif event.button == 3:  # RIGHT_MOUSE_BUTTON
                mp.add_reverse_org_search(event.pos)
        else:
            continue

        map_file = load_map(mp)
        screen.blit(pygame.image.load(map_file), (0, 0))

        if mp.search_result:
            text = render_text(str(mp.search_result))
            screen.blit(text, (20, 400))

        pygame.display.flip()

    pygame.quit()
    # os.remove(map_file)


if __name__ == "__main__":
    main()
