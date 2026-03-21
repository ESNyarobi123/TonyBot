<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Api\ApiController;

/*
|--------------------------------------------------------------------------
| ERICKsky Signal Engine — API Routes
|--------------------------------------------------------------------------
| All routes are rate-limited at 60 req/min.
| Returns JSON only.  No auth required (internal network only).
*/

Route::middleware('throttle:60,1')->prefix('api')->group(function () {

    // ── Core stats (polled every 10s by dashboard JS) ─────────────────────
    Route::get('/stats',    [ApiController::class, 'stats']);

    // ── Signals (list + detail + outcome) ─────────────────────────────────
    Route::get('/signals',           [ApiController::class, 'signals']);
    Route::get('/signals/{signal}',  [ApiController::class, 'signal']);
    Route::post('/signals/{signal}/outcome', [ApiController::class, 'recordOutcome']);

    // ── Performance analytics ──────────────────────────────────────────────
    Route::get('/performance',   [ApiController::class, 'performance']);

    // ── Institutional upgrade analytics ───────────────────────────────────
    Route::get('/regime-stats',  [ApiController::class, 'regimeStats']);
    Route::get('/filter-stats',  [ApiController::class, 'filterStats']);

    // ── News events from local DB (Upgrade 7) ─────────────────────────────
    Route::get('/news-events',   [ApiController::class, 'newsEvents']);
});
