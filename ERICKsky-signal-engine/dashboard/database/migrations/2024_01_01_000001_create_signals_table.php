<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (Schema::hasTable('signals')) {
            return;
        }

        Schema::create('signals', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->string('pair', 10);
            $table->string('direction', 4);
            $table->decimal('entry_price', 10, 5);
            $table->decimal('stop_loss', 10, 5);
            $table->decimal('take_profit_1', 10, 5);
            $table->decimal('take_profit_2', 10, 5)->nullable();
            $table->decimal('take_profit_3', 10, 5)->nullable();
            $table->string('timeframe', 5);
            $table->jsonb('strategy_scores')->default('{}');
            $table->integer('consensus_score');
            $table->string('confidence', 10);
            $table->jsonb('filters_passed')->default('{}');
            $table->string('status', 10)->default('PENDING');
            $table->decimal('pips_result', 6, 1)->nullable();
            $table->timestampTz('sent_at')->nullable();
            $table->timestampTz('closed_at')->nullable();
            $table->timestampTz('created_at')->default(now());

            $table->index('pair');
            $table->index('status');
            $table->index('created_at');
            $table->index('direction');
        });
    }


    public function down(): void
    {
        Schema::dropIfExists('signals');
    }
};
