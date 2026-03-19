<?php

return [

    'default' => env('CACHE_DRIVER', 'redis'),

    'stores' => [
        'redis' => [
            'driver'     => 'redis',
            'connection' => 'cache',
            'lock_connection' => 'default',
        ],
        'file' => [
            'driver' => 'file',
            'path'   => storage_path('framework/cache/data'),
            'lock_path' => storage_path('framework/cache/data'),
        ],
        'array' => [
            'driver'    => 'array',
            'serialize' => false,
        ],
    ],

    'prefix' => env('CACHE_PREFIX', 'erickskybot_cache'),

];
