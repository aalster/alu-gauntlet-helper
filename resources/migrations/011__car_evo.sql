-- Evo-авто: ранг піднімається вище max_rank evo-деталями, а не оверклоком
alter table cars add column evo integer not null default 0;
