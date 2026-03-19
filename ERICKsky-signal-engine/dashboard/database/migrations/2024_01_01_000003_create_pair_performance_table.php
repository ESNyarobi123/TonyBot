<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (Schema::hasTable('pair_performance')) {
            return;
        }

        Schema::create('pair_performance', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->string('pair', 10);
            $table->date('date');
            $table->integer('signals_sent')->default(0);
            $table->integer('wins')->default(0);
            $table->integer('losses')->default(0);
            $table->decimal('win_rate', 5, 2)->default(0.00);
            $table->decimal('total_pips', 8, 1)->default(0.0);
            $table->timestampTz('created_at')->default(now());

            $table->unique(['pair', 'date']);
            $table->index('pair');
            $table->index('date');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('pair_performance');
    }
};
