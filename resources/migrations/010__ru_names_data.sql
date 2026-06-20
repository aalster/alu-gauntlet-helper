-- Заповнення name_ru для наявних БД (нові БД отримують це із seed).
-- Лише порожні значення — правки користувача не чіпаємо. Треки матчимо за
-- глобально унікальною назвою з COLLATE NOCASE (стійко до дрейфу назв карт/регістру).

update maps set name_ru='Окленд' where name='Auckland' collate nocase and name_ru='';
update maps set name_ru='Буэнос-Айрес' where name='Buenos Aires' collate nocase and name_ru='';
update maps set name_ru='Каир' where name='Cairo' collate nocase and name_ru='';
update maps set name_ru='Гренландия' where name='Greenland' collate nocase and name_ru='';
update maps set name_ru='Гималаи' where name='Himalayas' collate nocase and name_ru='';
update maps set name_ru='Невада' where name='Nevada' collate nocase and name_ru='';
update maps set name_ru='Нью-Йорк' where name='New York' collate nocase and name_ru='';
update maps set name_ru='Норвегия' where name='Norway' collate nocase and name_ru='';
update maps set name_ru='Осака' where name='Osaka' collate nocase and name_ru='';
update maps set name_ru='Париж' where name='Paris' collate nocase and name_ru='';
update maps set name_ru='Рим' where name='Rome' collate nocase and name_ru='';
update maps set name_ru='Сан-Франциско' where name='San Francisco' collate nocase and name_ru='';
update maps set name_ru='Шотландия' where name='Scotland' collate nocase and name_ru='';
update maps set name_ru='Шанхай' where name='Shanghai' collate nocase and name_ru='';
update maps set name_ru='Сингапур' where name='Singapore' collate nocase and name_ru='';
update maps set name_ru='Карибы' where name='The Caribbean' collate nocase and name_ru='';
update maps set name_ru='Тоскана' where name='Tuscany' collate nocase and name_ru='';
update maps set name_ru='Ср. Запад США' where name='U.S. Midwest' collate nocase and name_ru='';

update tracks set name_ru='Крутой Финиш' where name='Hairpin Finish' collate nocase and name_ru='';
update tracks set name_ru='Спринт По Прямой' where name='Straight Sprint' collate nocase and name_ru='';
update tracks set name_ru='La Boca' where name='La Boca' collate nocase and name_ru='';
update tracks set name_ru='Водный Заезд' where name='Water Run' collate nocase and name_ru='';
update tracks set name_ru='Возвращение Короля' where name='A Kings Revival' collate nocase and name_ru='';
update tracks set name_ru='Остров Гезира' where name='Gezira Island' collate nocase and name_ru='';
update tracks set name_ru='Ледоломы' where name='Ice Breakers' collate nocase and name_ru='';
update tracks set name_ru='Из Центра' where name='Out of the Center' collate nocase and name_ru='';
update tracks set name_ru='Свободное Падение' where name='Freefall' collate nocase and name_ru='';
update tracks set name_ru='Прыжок Веры' where name='Leap of Faith' collate nocase and name_ru='';
update tracks set name_ru='От Моста К Мосту' where name='Bridge to Bridge' collate nocase and name_ru='';
update tracks set name_ru='Туннельный Спринт' where name='Tunnel Sprint' collate nocase and name_ru='';
update tracks set name_ru='Поездка По Уолл-Стрит' where name='Wall Street Ride' collate nocase and name_ru='';
update tracks set name_ru='Синтез Будущего' where name='Future Fusion' collate nocase and name_ru='';
update tracks set name_ru='Вперед В Будущее' where name='Rocketing to the Future' collate nocase and name_ru='';
update tracks set name_ru='Натиск Мэйдзи' where name='Meiji Rush' collate nocase and name_ru='';
update tracks set name_ru='Парк Намба' where name='Namba Park' collate nocase and name_ru='';
update tracks set name_ru='Вдоль Сены' where name='Along the Seine' collate nocase and name_ru='';
update tracks set name_ru='Нотр-Дам' where name='Notre Dame' collate nocase and name_ru='';
update tracks set name_ru='Римские Тропы' where name='Roman Byroads' collate nocase and name_ru='';
update tracks set name_ru='Римские Качели' where name='Roman Tumble' collate nocase and name_ru='';
update tracks set name_ru='Железная Дорога' where name='Railroad Bustle' collate nocase and name_ru='';
update tracks set name_ru='Тоннель' where name='The Tunnel' collate nocase and name_ru='';
update tracks set name_ru='Летучий Голландец' where name='Ghost Ships' collate nocase and name_ru='';
update tracks set name_ru='Каньон' where name='Rocky Valley' collate nocase and name_ru='';
update tracks set name_ru='Двойное Кольцо' where name='Double Roundabout' collate nocase and name_ru='';
update tracks set name_ru='Восточный Париж' where name='Paris of the East' collate nocase and name_ru='';
update tracks set name_ru='Городская Спешка' where name='Urban Rush' collate nocase and name_ru='';
update tracks set name_ru='Водоворот' where name='Waterslide Whirl' collate nocase and name_ru='';
update tracks set name_ru='Адская Долина' where name='Hell Vale' collate nocase and name_ru='';
update tracks set name_ru='Курортный Прорыв' where name='Resort Dash' collate nocase and name_ru='';
update tracks set name_ru='Вояж По Виноградникам' where name='Vineyard Voyage' collate nocase and name_ru='';
update tracks set name_ru='Старт На Берегу Реки' where name='Riverine Launch' collate nocase and name_ru='';
update tracks set name_ru='Вот Это Поворот!' where name='Its a Twister' collate nocase and name_ru='';
update tracks set name_ru='Рельсы' where name='Trainspotter' collate nocase and name_ru='';
