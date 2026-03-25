<?php

return [

    'class_namespace' => 'App\\Http\\Livewire',

    'view_path' => resource_path('views/livewire'),

    'layout' => 'layouts.app',

    'lazy_placeholder' => null,

    'temporary_file_upload' => [
        'disk'      => null,
        'rules'     => ['required', 'file', 'max:12288'],
        'directory' => null,
        'middleware' => 'throttle:60,1',
        'preview_mimes' => [
            'png', 'gif', 'bmp', 'svg', 'wav', 'mp4',
            'mov', 'avi', 'wmv', 'mp3', 'm4a', 'jpg',
            'jpeg', 'mpga', 'webp', 'wma',
        ],
        'max_upload_time' => 5,
    ],

    'render_on_redirect' => false,

    'navigate' => [
        'show_progress_bar' => true,
        'progress_bar_color' => '#2299dd',
    ],

    'inject_assets' => true,

    'inject_morph_markers' => true,

    'pagination_theme' => 'tailwind',

    'asset_url' => null,

    'app_url' => env('APP_URL', 'http://localhost'),

    'asset_base_url' => env('ASSET_URL', null),

];
