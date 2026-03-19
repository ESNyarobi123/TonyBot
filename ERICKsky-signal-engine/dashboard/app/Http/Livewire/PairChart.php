<?php

namespace App\Http\Livewire;

use App\Models\Signal;
use Livewire\Component;

class PairChart extends Component
{
    public string $pair = 'EURUSD';
    public string $timeframe = '1h';

    public array $pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD'];
    public array $timeframes = ['15min' => '15M', '1h' => '1H', '4h' => '4H', '1day' => '1D'];

    public function mount(string $pair = 'EURUSD'): void
    {
        $this->pair = $pair;
    }

    public function setPair(string $pair): void
    {
        $this->pair = $pair;
    }

    public function setTimeframe(string $tf): void
    {
        $this->timeframe = $tf;
    }

    public function getTradingViewSymbol(): string
    {
        return match ($this->pair) {
            'XAUUSD' => 'OANDA:XAUUSD',
            'USDJPY' => 'FX:USDJPY',
            'GBPUSD' => 'FX:GBPUSD',
            default   => 'FX:EURUSD',
        };
    }

    public function getTradingViewInterval(): string
    {
        return match ($this->timeframe) {
            '15min' => '15',
            '4h'    => '240',
            '1day'  => 'D',
            default => '60',
        };
    }

    public function getRecentSignals(): \Illuminate\Support\Collection
    {
        return Signal::where('pair', $this->pair)
            ->orderBy('created_at', 'desc')
            ->limit(5)
            ->get();
    }

    public function render()
    {
        $recentSignals    = $this->getRecentSignals();
        $tvSymbol         = $this->getTradingViewSymbol();
        $tvInterval       = $this->getTradingViewInterval();

        return view('livewire.pair-chart', compact('recentSignals', 'tvSymbol', 'tvInterval'));
    }
}
