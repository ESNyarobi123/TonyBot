<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'ERICKsky Signal Engine')</title>

    <!-- TailwindCSS + DaisyUI -->
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.6.0/dist/full.min.css" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

    <!-- Livewire -->
    @livewireStyles

    <style>
        .sidebar-link.active { @apply bg-primary text-primary-content; }
        .stat-ring { background: conic-gradient(#f59e0b calc(var(--pct) * 3.6deg), #374151 0deg); }
    </style>
</head>
<body class="bg-base-100 text-base-content min-h-screen">

<div class="drawer lg:drawer-open">
    <input id="drawer-toggle" type="checkbox" class="drawer-toggle">

    {{-- Main Content --}}
    <div class="drawer-content flex flex-col">

        {{-- Top Navbar --}}
        <nav class="navbar bg-base-200 shadow-md px-4 lg:px-6">
            <div class="flex-none lg:hidden">
                <label for="drawer-toggle" class="btn btn-ghost btn-square">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                         class="inline-block w-5 h-5 stroke-current">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M4 6h16M4 12h16M4 18h16"></path>
                    </svg>
                </label>
            </div>

            <div class="flex-1">
                <span class="text-lg font-bold text-primary">📡 ERICKsky Signal Engine</span>
            </div>

            <div class="flex-none gap-2">
                {{-- Bot Status --}}
                <div class="badge badge-success gap-1 hidden sm:flex">
                    <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                    RUNNING
                </div>
                {{-- UTC Clock --}}
                <div class="text-sm text-base-content/60 hidden md:block"
                     x-data="{ time: '' }"
                     x-init="setInterval(() => { time = new Date().toUTCString().slice(17,22) + ' UTC' }, 1000)">
                    <span x-text="time"></span>
                </div>
            </div>
        </nav>

        {{-- Page Content --}}
        <main class="flex-1 p-4 lg:p-6">
            @if (session('success'))
                <div class="alert alert-success mb-4">
                    <span>{{ session('success') }}</span>
                </div>
            @endif
            @if (session('error'))
                <div class="alert alert-error mb-4">
                    <span>{{ session('error') }}</span>
                </div>
            @endif

            @yield('content')
        </main>

        <footer class="footer footer-center p-4 bg-base-200 text-base-content/50 text-xs">
            <p>ERICKsky Signal Engine &copy; {{ date('Y') }} — All signals are for educational purposes only.</p>
        </footer>
    </div>

    {{-- Sidebar --}}
    <div class="drawer-side z-40">
        <label for="drawer-toggle" class="drawer-overlay"></label>
        <aside class="bg-base-200 w-64 min-h-full flex flex-col">

            {{-- Logo --}}
            <div class="p-6 border-b border-base-300">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-xl">📡</div>
                    <div>
                        <div class="font-bold text-sm">ERICKsky</div>
                        <div class="text-xs text-base-content/60">Signal Engine v1.0</div>
                    </div>
                </div>
            </div>

            {{-- Navigation --}}
            <ul class="menu menu-lg p-4 flex-1 gap-1">
                <li>
                    <a href="{{ route('dashboard') }}"
                       class="sidebar-link {{ request()->routeIs('dashboard') ? 'active' : '' }}">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                        </svg>
                        Dashboard
                    </a>
                </li>
                <li>
                    <a href="{{ route('signals.index') }}"
                       class="sidebar-link {{ request()->routeIs('signals.*') ? 'active' : '' }}">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                        </svg>
                        Signals
                    </a>
                </li>
                <li>
                    <a href="{{ route('subscribers.index') }}"
                       class="sidebar-link {{ request()->routeIs('subscribers.*') ? 'active' : '' }}">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
                        </svg>
                        Subscribers
                    </a>
                </li>
                <li>
                    <a href="{{ route('telegram.index') }}"
                       class="sidebar-link {{ request()->routeIs('telegram.*') ? 'active' : '' }}">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                        </svg>
                        Telegram
                    </a>
                </li>
                <li>
                    <a href="{{ route('performance.index') }}"
                       class="sidebar-link {{ request()->routeIs('performance.*') ? 'active' : '' }}">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                        </svg>
                        Performance
                    </a>
                </li>
            </ul>

            {{-- Bottom info --}}
            <div class="p-4 border-t border-base-300 text-xs text-base-content/40">
                <div>Trading Pairs: {{ implode(', ', config('trading.pairs', ['EURUSD','GBPUSD','USDJPY','XAUUSD'])) }}</div>
            </div>
        </aside>
    </div>
</div>

@livewireScripts

{{-- Auto-refresh Livewire every 10s --}}
<script>
    document.addEventListener('livewire:initialized', () => {
        setInterval(() => Livewire.dispatch('refreshSignals'), 10000);
    });
</script>

</body>
</html>
