create table settings (
    key   varchar(100) primary key,
    value varchar(255)
);

create table maps (
    id         integer primary key autoincrement,
    name       varchar(255) not null default '',
    created_at datetime     not null default current_timestamp
);

create unique index maps_name_uindex
    on maps (name);

create table tracks (
    id         integer primary key autoincrement,
    map_id     integer      not null,
    name       varchar(255) not null default '',
    created_at datetime     not null default current_timestamp
);

create unique index tracks_map_id_name_uindex
    on tracks (map_id, name);

create table cars (
    id         integer primary key autoincrement,
    name       varchar(255) not null default '',
    rank       integer      not null default 0,
    created_at datetime     not null default current_timestamp
);

create unique index cars_name_uindex
    on cars (name);

create table races (
    id         integer primary key autoincrement,
    track_id   integer  not null,
    car_id     integer  not null default 0,
    rank       integer  not null default 0,
    time       integer  not null default 0,
    created_at datetime not null default current_timestamp
);