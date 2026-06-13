# Оновлення даних про авто (ручне)

Застосунок **не ходить у мережу**: список авто та іконки зашиті в збірку, і при кожному
старті дані з бандла апсертяться в БД (`cars_sync.sync_bundled_cars`). Щоб підтягнути
нові авто з гри — онови бандл і перезбери інсталятор.

## Звідки беруться дані

| Що | Файл у репозиторії | Джерело |
|---|---|---|
| Список авто | `resources/data/cars.json` | `https://asec.tools/.netlify/functions/carsList` (GET, JSON-масив) |
| Іконки авто | `resources/icons/cars/{id}.webp` | `https://img.asec.tools/{id}.webp` (`id` — поле `id` з carsList) |
| Іконки карт | `resources/icons/maps/{Назва}.png` | вручну (скріншоти з гри) |

З carsList використовуються поля: `id` (зберігається як `asec_id`), `brand`, `model`,
`car_class`, `max_rank`. Решта ігнорується.

## Як застосунок споживає бандл

- **Список**: на кожному старті апсерт у БД — матчинг за `asec_id`, потім за іменем
  (`brand model`); оновлює клас/макс-ранг/іконку, додає нові авто. Видалені з carsList
  авто з БД не видаляються.
- **Іконки**: при синхронізації іконка копіюється з ресурсів збірки в `data/cars/{id}.webp`
  (тека поруч з exe) **тільки якщо її там ще немає**. Тобто якщо іконка в бандлі
  оновилась, стара копія в `data/cars/` виграє — щоб підхопити нову, видали відповідний
  файл із `data/cars/`.

## Процедура оновлення

1. Онови знімок списку:

   ```powershell
   Invoke-WebRequest "https://asec.tools/.netlify/functions/carsList" -OutFile "resources\data\cars.json"
   ```

2. Докачай іконки для нових авто (тільки відсутні):

   ```powershell
   $cars = Get-Content "resources\data\cars.json" -Raw | ConvertFrom-Json
   foreach ($c in $cars) {
       $dst = "resources\icons\cars\$($c.id).webp"
       if (-not (Test-Path $dst)) {
           Invoke-WebRequest "https://img.asec.tools/$($c.id).webp" -OutFile $dst
       }
   }
   ```

3. Перезбери інсталятор: `powershell -File scripts/build_installer.ps1` — і встанови поверх.
   Нові авто з'являться при наступному запуску застосунку.
