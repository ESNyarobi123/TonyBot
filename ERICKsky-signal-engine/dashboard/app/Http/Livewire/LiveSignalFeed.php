<?php

namespace App\Http\Livewire;

use App\Models\Signal;
use Livewire\Component;

class LiveSignalFeed extends Component
{
    public int $limit = 10;
    public string $filterPair = '';
    public string $filterDirection = '';

    protected $listeners = ['refreshSignals' => '$refresh'];

    public function render()
    {
        $query = Signal::orderBy('created_at', 'desc');

        if ($this->filterPair) {
            $query->where('pair', $this->filterPair);
        }
        if ($this->filterDirection) {
            $query->where('direction', $this->filterDirection);
        }

        $signals = $query->limit($this->limit)->get();
        $pairs   = Signal::select('pair')->distinct()->pluck('pair');

        return view('livewire.live-signal-feed', compact('signals', 'pairs'));
    }

    public function loadMore(): void
    {
        $this->limit += 10;
    }
}
