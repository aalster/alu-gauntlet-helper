create table maps (
    id         integer primary key autoincrement,
    name       varchar(255) not null default '',
    created_at datetime     not null default current_timestamp
);

create table tracks (
    id         integer primary key autoincrement,
    map_id     integer      not null,
    name       varchar(255) not null default '',
    created_at datetime     not null default current_timestamp
);

create table cars (
    id         integer primary key autoincrement,
    name       varchar(255) not null default '',
    rank       integer      not null default 0,
    created_at datetime     not null default current_timestamp
);

create table races (
    id         integer primary key autoincrement,
    track_id   integer      not null,
    car_id     integer not null default 0,
    rank       integer not null default 0,
    time       integer not null default 0,
    created_at datetime     not null default current_timestamp
);