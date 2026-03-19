<?php

namespace App\Http\Livewire;

use App\Models\Subscriber;
use Livewire\Component;
use Livewire\WithPagination;

class SubscriberTable extends Component
{
    use WithPagination;

    public string $search = '';
    public string $planFilter = '';
    public string $sortField = 'created_at';
    public string $sortDirection = 'desc';

    protected $queryString = ['search', 'planFilter'];

    public function updatingSearch(): void
    {
        $this->resetPage();
    }

    public function sortBy(string $field): void
    {
        if ($this->sortField === $field) {
            $this->sortDirection = $this->sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            $this->sortField     = $field;
            $this->sortDirection = 'asc';
        }
    }

    public function deactivate(int $id): void
    {
        Subscriber::find($id)?->update(['is_active' => false]);
        $this->dispatch('subscriber-updated');
    }

    public function render()
    {
        $query = Subscriber::query();

        if ($this->search) {
            $query->where(function ($q) {
                $q->where('username', 'ilike', "%{$this->search}%")
                  ->orWhere('full_name', 'ilike', "%{$this->search}%")
                  ->orWhere('telegram_chat_id', 'ilike', "%{$this->search}%");
            });
        }

        if ($this->planFilter) {
            $query->where('plan', $this->planFilter);
        }

        $subscribers = $query
            ->orderBy($this->sortField, $this->sortDirection)
            ->paginate(20);

        return view('livewire.subscriber-table', compact('subscribers'));
    }
}
