@props(['title', 'value', 'subtitle' => null, 'color' => 'text-primary', 'icon' => null])

<div class="stat bg-base-200 rounded-xl p-5 shadow hover:shadow-lg transition-shadow">
    @if($icon)
    <div class="stat-figure {{ $color }} text-3xl">{{ $icon }}</div>
    @endif
    <div class="stat-title text-xs text-base-content/60">{{ $title }}</div>
    <div class="stat-value text-2xl font-bold {{ $color }}">{{ $value }}</div>
    @if($subtitle)
    <div class="stat-desc text-xs text-base-content/50 mt-1">{{ $subtitle }}</div>
    @endif
</div>
