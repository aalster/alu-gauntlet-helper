-- Нові карти й треки з оновлення гри (жовтень 2026) для наявних БД; нові БД отримують
-- їх із seed (services/initial_data.py). Унікальні індекси maps(name) і tracks(map_id, name)
-- роблять повторний запуск і збіг із вручну доданими записами безпечним (insert or ignore).
-- Іконки карт/треків підтягуються з бандла на старті (initial_data.sync_track_icons).

-- Mt. Fuji у рос. версії гри без перекладу (порожній name_ru → показ англійською).

insert or ignore into maps (name, name_ru) values ('Chicago', 'Чикаго');
insert or ignore into maps (name, name_ru) values ('San Diego', 'Сан-Диего');
insert or ignore into maps (name, name_ru) values ('India', 'Индия');
insert or ignore into maps (name, name_ru) values ('Mt. Fuji', '');

insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Ironclad Descent', 'Жесткая Посадка' from maps where name = 'Chicago' collate nocase;
insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Echo Drift', 'Эходрифт' from maps where name = 'Chicago' collate nocase;
insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Container Chaos', 'Контейнерный Хаос' from maps where name = 'San Diego' collate nocase;
insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Pacific Rampage', 'Океаническая Ярость' from maps where name = 'San Diego' collate nocase;
insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Gravel Grooves', 'Гравиевые Дороги' from maps where name = 'India' collate nocase;
insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Rock Terrain', 'Скалистая Местность' from maps where name = 'India' collate nocase;
insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Countryside Sprint', 'Деревенский Спринт' from maps where name = 'Mt. Fuji' collate nocase;
insert or ignore into tracks (map_id, name, name_ru)
    select id, 'Bullet Train Sprint', 'Молниеносный Спринт' from maps where name = 'Mt. Fuji' collate nocase;
