<?php

return [

    'default' => env('DB_CONNECTION', 'pgsql'),

    'connections' => [

        'pgsql' => [
            'driver'   => 'pgsql',
            'url'      => env('DATABASE_URL'),
            'host'     => env('DB_HOST', 'postgres'),
            'port'     => env('DB_PORT', '5432'),
            'database' => env('DB_DATABASE', 'erickskybot'),
            'username' => env('DB_USERNAME', 'erickskybot'),
            'password' => env('DB_PASSWORD', ''),
            'charset'  => 'utf8',
            'prefix'   => '',
            'prefix_indexes' => true,
            'search_path'    => 'public',
            'sslmode'        => 'prefer',
        ],

    ],

    'migrations' => [
        'table' => 'migrations',
        'update_date_on_publish' => true,
    ],

    'redis' => [
        'client' => env('REDIS_CLIENT', 'predis'),
        'default' => [
            'host'     => env('REDIS_HOST', 'redis'),
            'password' => env('REDIS_PASSWORD', null),
            'port'     => env('REDIS_PORT', '6379'),
            'database' => env('REDIS_DB', '0'),
        ],
        'cache' => [
            'host'     => env('REDIS_HOST', 'redis'),
            'password' => env('REDIS_PASSWORD', null),
            'port'     => env('REDIS_PORT', '6379'),
            'database' => env('REDIS_CACHE_DB', '1'),
        ],
    ],

];
