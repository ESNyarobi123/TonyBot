<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class PairPerformance extends Model
{
    protected $table = 'pair_performance';

    protected $fillable = [
        'pair', 'date', 'signals_sent', 'wins', 'losses', 'win_rate', 'total_pips',
    ];

    protected $casts = [
        'date'         => 'date',
        'signals_sent' => 'integer',
        'wins'         => 'integer',
        'losses'       => 'integer',
        'win_rate'     => 'float',
        'total_pips'   => 'float',
        'created_at'   => 'datetime',
    ];

    public $timestamps = false;
}
