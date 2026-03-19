<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Builder;

class Subscriber extends Model
{
    protected $table = 'subscribers';

    protected $fillable = [
        'telegram_chat_id', 'username', 'full_name', 'plan',
        'subscribed_at', 'expires_at', 'is_active', 'total_signals_received',
    ];

    protected $casts = [
        'is_active'               => 'boolean',
        'total_signals_received'  => 'integer',
        'subscribed_at'           => 'datetime',
        'expires_at'              => 'datetime',
        'created_at'              => 'datetime',
    ];

    public $timestamps = false;

    // ── Scopes ─────────────────────────────────────────────────────────────────

    public function scopeActive(Builder $query): Builder
    {
        return $query->where('is_active', true);
    }

    public function scopePremium(Builder $query): Builder
    {
        return $query->where('plan', 'PREMIUM')
                     ->where('is_active', true)
                     ->where(function ($q) {
                         $q->whereNull('expires_at')
                           ->orWhere('expires_at', '>', now());
                     });
    }

    // ── Accessors ──────────────────────────────────────────────────────────────

    public function getDisplayNameAttribute(): string
    {
        return $this->full_name ?? $this->username ?? "User {$this->telegram_chat_id}";
    }

    public function getPlanBadgeAttribute(): string
    {
        return match ($this->plan) {
            'PREMIUM' => 'badge-warning',
            'BASIC'   => 'badge-info',
            default   => 'badge-neutral',
        };
    }

    public function getIsExpiredAttribute(): bool
    {
        return $this->expires_at && $this->expires_at->isPast();
    }
}
