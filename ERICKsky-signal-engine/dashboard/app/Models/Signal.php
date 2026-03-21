<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Builder;

class Signal extends Model
{
    protected $table = 'signals';

    protected $fillable = [
        'pair', 'direction', 'entry_price', 'stop_loss',
        'take_profit_1', 'take_profit_2', 'take_profit_3',
        'timeframe', 'strategy_scores', 'strategy_directions',
        'consensus_score', 'confidence', 'filters_passed', 'status',
        'pips_result', 'sent_at', 'closed_at',
        // Institutional upgrade fields (migration_002)
        'm15_confirmed', 'm15_score', 'market_regime', 'pattern_names',
    ];

    protected $casts = [
        'entry_price'         => 'float',
        'stop_loss'           => 'float',
        'take_profit_1'       => 'float',
        'take_profit_2'       => 'float',
        'take_profit_3'       => 'float',
        'strategy_scores'     => 'array',
        'strategy_directions' => 'array',
        'filters_passed'      => 'array',
        'pattern_names'       => 'array',
        'consensus_score'     => 'integer',
        'm15_score'           => 'integer',
        'm15_confirmed'       => 'boolean',
        'pips_result'         => 'float',
        'sent_at'             => 'datetime',
        'closed_at'           => 'datetime',
        'created_at'          => 'datetime',
    ];

    public $timestamps = false;

    // ── Scopes ─────────────────────────────────────────────────────────────────

    public function scopePending(Builder $query): Builder
    {
        return $query->where('status', 'PENDING');
    }

    public function scopeToday(Builder $query): Builder
    {
        return $query->whereDate('created_at', today());
    }

    public function scopeByPair(Builder $query, string $pair): Builder
    {
        return $query->where('pair', $pair);
    }

    public function scopeWins(Builder $query): Builder
    {
        return $query->where('status', 'WIN');
    }

    public function scopeLosses(Builder $query): Builder
    {
        return $query->where('status', 'LOSS');
    }

    // Institutional upgrade scopes
    public function scopeByRegime(Builder $query, string $regime): Builder
    {
        return $query->where('market_regime', $regime);
    }

    public function scopeM15Confirmed(Builder $query): Builder
    {
        return $query->where('m15_confirmed', true);
    }

    public function scopeWithPattern(Builder $query): Builder
    {
        return $query->whereNotNull('pattern_names')
            ->whereRaw("pattern_names::text != '[]'");
    }

    public function scopeHighConfidence(Builder $query): Builder
    {
        return $query->whereIn('confidence', ['HIGH', 'VERY_HIGH']);
    }

    // ── Accessors ──────────────────────────────────────────────────────────────

    public function getDirectionBadgeAttribute(): string
    {
        return match ($this->direction) {
            'BUY'   => 'badge-success',
            'SELL'  => 'badge-error',
            default => 'badge-neutral',
        };
    }

    public function getStatusBadgeAttribute(): string
    {
        return match ($this->status) {
            'WIN'     => 'badge-success',
            'LOSS'    => 'badge-error',
            'PENDING' => 'badge-warning',
            'EXPIRED' => 'badge-neutral',
            default   => 'badge-neutral',
        };
    }

    public function getConfidenceBadgeAttribute(): string
    {
        return match ($this->confidence) {
            'VERY_HIGH' => 'badge-error',
            'HIGH'      => 'badge-warning',
            'MEDIUM'    => 'badge-info',
            default     => 'badge-neutral',
        };
    }

    public function getRegimeBadgeAttribute(): string
    {
        return match ($this->market_regime) {
            'TRENDING'   => 'badge-success',
            'WEAK_TREND' => 'badge-info',
            'RANGING'    => 'badge-warning',
            'VOLATILE'   => 'badge-error',
            default      => 'badge-ghost',
        };
    }

    public function getM15BadgeAttribute(): string
    {
        if ($this->m15_confirmed === null) return 'badge-ghost';
        return $this->m15_confirmed ? 'badge-success' : 'badge-warning';
    }

    public function getPatternDisplayAttribute(): string
    {
        $patterns = $this->pattern_names ?? [];
        if (empty($patterns)) return '—';
        return implode(', ', array_map(
            fn($p) => str_replace('_', ' ', $p),
            $patterns
        ));
    }

    public function getStrategyAgreementAttribute(): string
    {
        $scores = $this->strategy_scores ?? [];
        $dirs   = $this->strategy_directions ?? [];
        if (empty($scores)) return '—';
        $agree = count(array_filter(
            $dirs,
            fn($d) => $d === $this->direction
        ));
        return "{$agree}/" . count($scores);
    }

    public function getRiskRewardAttribute(): string
    {
        if (! $this->take_profit_1 || ! $this->stop_loss) return 'N/A';
        $slDist = abs($this->entry_price - $this->stop_loss);
        $tpDist = abs($this->take_profit_1 - $this->entry_price);
        if ($slDist == 0) return 'N/A';
        return '1:' . number_format($tpDist / $slDist, 1);
    }
}
