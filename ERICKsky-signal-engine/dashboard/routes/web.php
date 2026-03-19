<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\SignalController;
use App\Http\Controllers\SubscriberController;
use App\Http\Controllers\TelegramController;
use App\Http\Controllers\PerformanceController;

Route::get('/', [DashboardController::class, 'index'])->name('dashboard');

Route::prefix('signals')->name('signals.')->group(function () {
    Route::get('/',         [SignalController::class, 'index'])->name('index');
    Route::patch('/{signal}', [SignalController::class, 'update'])->name('update');
    Route::get('/export',   [SignalController::class, 'exportCsv'])->name('export');
});

Route::prefix('subscribers')->name('subscribers.')->group(function () {
    Route::get('/',              [SubscriberController::class, 'index'])->name('index');
    Route::post('/',             [SubscriberController::class, 'store'])->name('store');
    Route::patch('/{subscriber}',[SubscriberController::class, 'update'])->name('update');
    Route::delete('/{subscriber}',[SubscriberController::class, 'destroy'])->name('destroy');
});

Route::prefix('telegram')->name('telegram.')->group(function () {
    Route::get('/',                         [TelegramController::class, 'index'])->name('index');
    Route::post('/',                        [TelegramController::class, 'store'])->name('store');
    Route::post('/test',                    [TelegramController::class, 'sendTest'])->name('test');
    Route::patch('/{channel}/toggle',       [TelegramController::class, 'toggle'])->name('toggle');
    Route::delete('/{channel}',             [TelegramController::class, 'destroy'])->name('destroy');
});

Route::get('/performance', [PerformanceController::class, 'index'])->name('performance.index');
