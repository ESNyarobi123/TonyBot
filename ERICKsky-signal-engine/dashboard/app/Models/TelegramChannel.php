<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class TelegramChannel extends Model
{
    protected $table = 'telegram_channels';

    protected $fillable = [
        'channel_name', 'chat_id', 'type', 'is_active', 'subscribers_count',
    ];

    protected $casts = [
        'is_active'         => 'boolean',
        'subscribers_count' => 'integer',
        'created_at'        => 'datetime',
    ];

    public $timestamps = false;

    public function getTypeBadgeAttribute(): string
    {
        return $this->type === 'PREMIUM' ? 'badge-warning' : 'badge-neutral';
    }
}
