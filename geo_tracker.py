import math
from typing import Optional


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Вычисляет расстояние между двумя координатами GPS в метрах по формуле гаверсинусов.
    """
    R = 6371000.0  # Радиус Земли в метрах
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def calculate_steps_and_calories(
    distance_meters: float,
    step_length_meters: float = 0.75,
    weight_kg: float = 70.0,
) -> tuple[int, float]:
    """
    Конвертирует пройденное расстояние в шаги и примерные сожженные килокалории.
    Средняя длина шага: ~0.75 м.
    Калории: ~0.04 ккал на шаг (или ~0.75 ккал/кг/км при ходьбе).
    """
    steps = int(distance_meters / step_length_meters)
    distance_km = distance_meters / 1000.0
    # Формула расхода энергии при умеренной ходьбе: вес (кг) * 0.75 * км
    calories = weight_kg * 0.75 * distance_km
    return steps, round(calories, 1)
