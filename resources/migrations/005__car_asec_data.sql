alter table cars add column asec_id   integer      not null default 0;
alter table cars add column brand     varchar(255) not null default '';
alter table cars add column model     varchar(255) not null default '';
alter table cars add column car_class varchar(10)  not null default '';
alter table cars add column max_rank  integer      not null default 0;

create unique index cars_asec_id_uindex
    on cars (asec_id) where asec_id > 0;
