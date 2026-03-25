from dataclasses import dataclass, field
from typing import Optional, List, Dict
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("ERICKsky")

@dataclass
class SwingPoint:
    index: int
    price: float
    type: str
    strength: float

@dataclass 
class OrderBlock:
    type: str
    high: float
    low: float
    midpoint: float
    index: int
    valid: bool
    strength: float

@dataclass
class FairValueGap:
    type: str
    high: float
    low: float
    midpoint: float
    filled: bool
    index: int

@dataclass
class LiquidityZone:
    type: str
    price: float
    touches: int
    swept: bool

@dataclass
class MarketStructure:
    bias: str
    bos_type: Optional[str]
    bos_level: Optional[float]
    bos_strength: float
    choch_detected: bool
    choch_level: Optional[float]
    swing_highs: List[SwingPoint]
    swing_lows: List[SwingPoint]
    hh_hl: bool
    lh_ll: bool

@dataclass
class SharedMarketContext:
    symbol: str
    structure: MarketStructure
    order_blocks: List[OrderBlock]
    nearest_bullish_ob: Optional[OrderBlock]
    nearest_bearish_ob: Optional[OrderBlock]
    price_at_ob: bool
    ob_type_at_price: Optional[str]
    fvgs: List[FairValueGap]
    nearest_bull_fvg: Optional[FairValueGap]
    nearest_bear_fvg: Optional[FairValueGap]
    price_in_fvg: bool
    liquidity_zones: List[LiquidityZone]
    recent_liquidity_swept: bool
    swept_direction: Optional[str]
    key_support_levels: List[float]
    key_resistance_levels: List[float]
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    d1_trend: str
    h4_trend: str
    h1_trend: str
    atr_h1: float
    atr_h4: float
    current_price: float
    complete_smc_setup: bool
    smc_setup_direction: Optional[str]
    smc_setup_score: float

class MarketContextBuilder:
    
    def build(self, symbol: str, data: dict) -> SharedMarketContext:
        df_d1 = data.get("D1")
        df_h4 = data.get("H4")
        df_h1 = data.get("H1")
        
        current_price = float(df_h1['close'].values[-1])
        
        structure = self._build_structure(df_h4)
        obs = self._find_order_blocks(df_h4, structure)
        fvgs = self._find_fvgs(df_h1)
        liquidity = self._find_liquidity(df_h4)
        key_levels = self._find_key_levels(df_h4, df_h1)
        trends = self._get_trends(df_d1, df_h4, df_h1)
        atrs = self._get_atrs(df_h4, df_h1)
        
        bull_ob = self._nearest_ob(obs, current_price, "BULLISH_OB")
        bear_ob = self._nearest_ob(obs, current_price, "BEARISH_OB")
        
        at_ob, ob_type = self._price_at_ob(current_price, bull_ob, bear_ob)
        
        bull_fvg = self._nearest_fvg(fvgs, current_price, "BULL_FVG")
        bear_fvg = self._nearest_fvg(fvgs, current_price, "BEAR_FVG")
        
        in_fvg = self._price_in_fvg(current_price, bull_fvg, bear_fvg)
        
        swept, swept_dir = self._check_liquidity_sweep(liquidity, df_h1)
        
        smc_setup, smc_dir, smc_score = self._detect_complete_smc(
            structure, at_ob, ob_type, in_fvg, swept, swept_dir, bull_ob, bear_ob
        )
        
        ctx = SharedMarketContext(
            symbol=symbol,
            structure=structure,
            order_blocks=obs,
            nearest_bullish_ob=bull_ob,
            nearest_bearish_ob=bear_ob,
            price_at_ob=at_ob,
            ob_type_at_price=ob_type,
            fvgs=fvgs,
            nearest_bull_fvg=bull_fvg,
            nearest_bear_fvg=bear_fvg,
            price_in_fvg=in_fvg,
            liquidity_zones=liquidity,
            recent_liquidity_swept=swept,
            swept_direction=swept_dir,
            key_support_levels=key_levels["support"],
            key_resistance_levels=key_levels["resistance"],
            nearest_support=key_levels["nearest_support"],
            nearest_resistance=key_levels["nearest_resistance"],
            d1_trend=trends["d1"],
            h4_trend=trends["h4"],
            h1_trend=trends["h1"],
            atr_h1=atrs["h1"],
            atr_h4=atrs["h4"],
            current_price=current_price,
            complete_smc_setup=smc_setup,
            smc_setup_direction=smc_dir,
            smc_setup_score=smc_score,
        )
        
        self._log_context(ctx)
        return ctx
    
    def _build_structure(self, df_h4):
        highs = df_h4['high'].values
        lows = df_h4['low'].values
        closes = df_h4['close'].values
        
        swing_highs = []
        swing_lows = []
        
        for i in range(3, len(closes)-3):
            if all(highs[i] > highs[i-j] for j in range(1,4)) and \
               all(highs[i] > highs[i+j] for j in range(1,4)):
                swing_highs.append(SwingPoint(
                    index=i, price=highs[i], type="HIGH",
                    strength=float(highs[i] - np.mean(highs[max(0,i-5):i]))
                ))
            
            if all(lows[i] < lows[i-j] for j in range(1,4)) and \
               all(lows[i] < lows[i+j] for j in range(1,4)):
                swing_lows.append(SwingPoint(
                    index=i, price=lows[i], type="LOW",
                    strength=float(np.mean(lows[max(0,i-5):i]) - lows[i])
                ))
        
        swing_highs = swing_highs[-5:]
        swing_lows = swing_lows[-5:]
        
        hh_hl = False
        lh_ll = False
        
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            hh = swing_highs[-1].price > swing_highs[-2].price
            hl = swing_lows[-1].price > swing_lows[-2].price
            hh_hl = hh and hl
            
            lh = swing_highs[-1].price < swing_highs[-2].price
            ll = swing_lows[-1].price < swing_lows[-2].price
            lh_ll = lh and ll
        
        if hh_hl:
            bias = "BULLISH"
        elif lh_ll:
            bias = "BEARISH"
        else:
            bias = "RANGING"
        
        bos_type = None
        bos_level = None
        bos_strength = 0.0
        
        if len(swing_highs) >= 2:
            prev_high = swing_highs[-2].price
            if closes[-1] > prev_high:
                bos_type = "BULLISH"
                bos_level = prev_high
                bos_strength = float((closes[-1] - prev_high) / prev_high * 100)
        
        if len(swing_lows) >= 2 and not bos_type:
            prev_low = swing_lows[-2].price
            if closes[-1] < prev_low:
                bos_type = "BEARISH"
                bos_level = prev_low
                bos_strength = float((prev_low - closes[-1]) / prev_low * 100)
        
        # Persistent Bias: BOS keeps bias active for 8 candles during retracements
        if bias == "RANGING" and bos_type is not None:
            bos_candle_idx = max(
                (sp.index for sp in swing_highs + swing_lows),
                default=0,
            )
            candles_since_bos = len(closes) - 1 - bos_candle_idx
            if candles_since_bos <= 8:
                bias = "BULLISH" if bos_type == "BULLISH" else "BEARISH"
                logger.info(
                    f"MarketContext: Persistent bias override → {bias} "
                    f"(BOS {bos_type} still active, {candles_since_bos} candles ago)"
                )
        
        # Relax Ranging Filter: ADX > 20 with positive slope → TRENDING
        if bias == "RANGING" and len(closes) >= 28:
            adx_val, adx_slope = self._calc_adx(highs, lows, closes)
            if adx_val > 20 and adx_slope > 0:
                # Use EMA direction to determine trend
                ema20 = self._ema(closes, 20)
                if ema20[-1] > ema20[-5]:
                    bias = "BULLISH"
                else:
                    bias = "BEARISH"
                logger.info(
                    f"MarketContext: ADX override → {bias} "
                    f"(ADX={adx_val:.1f}, slope={adx_slope:.3f})"
                )
        
        choch_detected = False
        choch_level = None
        
        if bias == "BULLISH" and bos_type == "BEARISH":
            choch_detected = True
            choch_level = bos_level
        elif bias == "BEARISH" and bos_type == "BULLISH":
            choch_detected = True
            choch_level = bos_level
        
        return MarketStructure(
            bias=bias,
            bos_type=bos_type,
            bos_level=bos_level,
            bos_strength=bos_strength,
            choch_detected=choch_detected,
            choch_level=choch_level,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            hh_hl=hh_hl,
            lh_ll=lh_ll,
        )
    
    def _find_order_blocks(self, df_h4, structure):
        opens = df_h4['open'].values
        closes = df_h4['close'].values
        highs = df_h4['high'].values
        lows = df_h4['low'].values
        
        obs = []
        
        for i in range(1, len(closes)-3):
            candle_body = abs(opens[i] - closes[i])
            if candle_body < 1e-10:
                continue
            
            if closes[i] < opens[i]:
                # Smarter OB: Accept 1-2 impulse candles if move > 1.5x OB body
                best_impulse = 0.0
                best_n = 0
                for n_candles in range(1, 4):
                    end_idx = min(i + n_candles, len(closes) - 1)
                    if end_idx <= i:
                        continue
                    up_candles = all(
                        closes[i+j] > opens[i+j]
                        for j in range(1, n_candles + 1)
                        if i+j < len(closes)
                    )
                    if up_candles:
                        impulse = closes[end_idx] - closes[i]
                        if impulse > best_impulse:
                            best_impulse = impulse
                            best_n = n_candles
                
                # Accept if: 3 candles + impulse > 2x body (original)
                # OR: 1-2 candles + significant impulse > 1.5x body
                valid_ob = False
                if best_n >= 3 and best_impulse > candle_body * 2:
                    valid_ob = True
                elif best_n >= 1 and best_impulse > candle_body * 1.5:
                    valid_ob = True
                
                if valid_ob:
                    end_idx = min(i + best_n, len(closes) - 1)
                    violated = any(
                        closes[j] < lows[i]
                        for j in range(end_idx + 1, len(closes))
                    )
                    
                    obs.append(OrderBlock(
                        type="BULLISH_OB",
                        high=highs[i],
                        low=lows[i],
                        midpoint=(highs[i]+lows[i])/2,
                        index=i,
                        valid=not violated,
                        strength=min(100.0, float(best_impulse / candle_body * 30))
                    ))
            
            elif closes[i] > opens[i]:
                best_impulse = 0.0
                best_n = 0
                for n_candles in range(1, 4):
                    end_idx = min(i + n_candles, len(closes) - 1)
                    if end_idx <= i:
                        continue
                    down_candles = all(
                        closes[i+j] < opens[i+j]
                        for j in range(1, n_candles + 1)
                        if i+j < len(closes)
                    )
                    if down_candles:
                        impulse = closes[i] - closes[end_idx]
                        if impulse > best_impulse:
                            best_impulse = impulse
                            best_n = n_candles
                
                valid_ob = False
                if best_n >= 3 and best_impulse > candle_body * 2:
                    valid_ob = True
                elif best_n >= 1 and best_impulse > candle_body * 1.5:
                    valid_ob = True
                
                if valid_ob:
                    end_idx = min(i + best_n, len(closes) - 1)
                    violated = any(
                        closes[j] > highs[i]
                        for j in range(end_idx + 1, len(closes))
                    )
                    
                    obs.append(OrderBlock(
                        type="BEARISH_OB",
                        high=highs[i],
                        low=lows[i],
                        midpoint=(highs[i]+lows[i])/2,
                        index=i,
                        valid=not violated,
                        strength=min(100.0, float(best_impulse / candle_body * 30))
                    ))
        
        return [ob for ob in obs if ob.valid][-10:]
    
    def _find_fvgs(self, df_h1):
        highs = df_h1['high'].values
        lows = df_h1['low'].values
        closes = df_h1['close'].values
        
        fvgs = []
        
        for i in range(len(closes)-50, len(closes)-2):
            if i < 0:
                continue
            
            if lows[i+2] > highs[i]:
                gap_size = lows[i+2] - highs[i]
                filled = any(
                    lows[j] <= highs[i]
                    for j in range(i+2, len(lows))
                )
                fvgs.append(FairValueGap(
                    type="BULL_FVG",
                    high=lows[i+2],
                    low=highs[i],
                    midpoint=(lows[i+2]+highs[i])/2,
                    filled=filled,
                    index=i,
                ))
            
            elif highs[i+2] < lows[i]:
                gap_size = lows[i] - highs[i+2]
                filled = any(
                    highs[j] >= lows[i]
                    for j in range(i+2, len(highs))
                )
                fvgs.append(FairValueGap(
                    type="BEAR_FVG",
                    high=lows[i],
                    low=highs[i+2],
                    midpoint=(lows[i]+highs[i+2])/2,
                    filled=filled,
                    index=i,
                ))
        
        return [f for f in fvgs if not f.filled][-10:]
    
    def _find_liquidity(self, df_h4):
        highs = df_h4['high'].values
        lows = df_h4['low'].values
        
        liquidity = []
        
        for i in range(len(highs)-20, len(highs)):
            if i < 5:
                continue
            
            recent_highs = highs[max(0, i-10):i]
            recent_lows = lows[max(0, i-10):i]
            
            if len(recent_highs) > 0:
                max_high = np.max(recent_highs)
                touches = np.sum(np.abs(highs[max(0, i-10):i] - max_high) < 0.0001)
                swept = highs[i] > max_high
                
                if touches >= 2:
                    liquidity.append(LiquidityZone(
                        type="SELL_SIDE",
                        price=max_high,
                        touches=int(touches),
                        swept=swept
                    ))
            
            if len(recent_lows) > 0:
                min_low = np.min(recent_lows)
                touches = np.sum(np.abs(lows[max(0, i-10):i] - min_low) < 0.0001)
                swept = lows[i] < min_low
                
                if touches >= 2:
                    liquidity.append(LiquidityZone(
                        type="BUY_SIDE",
                        price=min_low,
                        touches=int(touches),
                        swept=swept
                    ))
        
        return liquidity[-10:]
    
    def _find_key_levels(self, df_h4, df_h1):
        highs_h4 = df_h4['high'].values
        lows_h4 = df_h4['low'].values
        current = df_h1['close'].values[-1]
        
        support_levels = []
        resistance_levels = []
        
        for i in range(5, len(lows_h4)-5):
            if all(lows_h4[i] < lows_h4[i-j] for j in range(1, 6)) and \
               all(lows_h4[i] < lows_h4[i+j] for j in range(1, 6)):
                support_levels.append(float(lows_h4[i]))
            
            if all(highs_h4[i] > highs_h4[i-j] for j in range(1, 6)) and \
               all(highs_h4[i] > highs_h4[i+j] for j in range(1, 6)):
                resistance_levels.append(float(highs_h4[i]))
        
        support_levels = sorted(support_levels)[-5:]
        resistance_levels = sorted(resistance_levels)[-5:]
        
        nearest_support = None
        nearest_resistance = None
        
        supports_below = [s for s in support_levels if s < current]
        if supports_below:
            nearest_support = max(supports_below)
        
        resistances_above = [r for r in resistance_levels if r > current]
        if resistances_above:
            nearest_resistance = min(resistances_above)
        
        return {
            "support": support_levels,
            "resistance": resistance_levels,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance
        }
    
    def _get_trends(self, df_d1, df_h4, df_h1):
        def trend_direction(df):
            closes = df['close'].values
            if len(closes) < 20:
                return "RANGING"
            
            ema20 = self._ema(closes, 20)
            ema50 = self._ema(closes, 50)
            
            if ema20[-1] > ema50[-1] and closes[-1] > ema20[-1]:
                return "UP"
            elif ema20[-1] < ema50[-1] and closes[-1] < ema20[-1]:
                return "DOWN"
            return "RANGING"
        
        return {
            "d1": trend_direction(df_d1),
            "h4": trend_direction(df_h4),
            "h1": trend_direction(df_h1)
        }
    
    def _get_atrs(self, df_h4, df_h1):
        def calc_atr(df, period=14):
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            
            tr = np.maximum(
                highs[1:] - lows[1:],
                np.maximum(
                    np.abs(highs[1:] - closes[:-1]),
                    np.abs(lows[1:] - closes[:-1])
                )
            )
            
            if len(tr) < period:
                return float(np.mean(tr))
            
            atr = np.zeros(len(tr))
            atr[period-1] = np.mean(tr[:period])
            
            for i in range(period, len(tr)):
                atr[i] = (atr[i-1] * (period-1) + tr[i]) / period
            
            return float(atr[-1])
        
        return {
            "h4": calc_atr(df_h4),
            "h1": calc_atr(df_h1)
        }
    
    def _nearest_ob(self, obs, current_price, ob_type):
        matching_obs = [ob for ob in obs if ob.type == ob_type and ob.valid]
        if not matching_obs:
            return None
        
        if ob_type == "BULLISH_OB":
            obs_below = [ob for ob in matching_obs if ob.high < current_price]
            if obs_below:
                return max(obs_below, key=lambda x: x.high)
        else:
            obs_above = [ob for ob in matching_obs if ob.low > current_price]
            if obs_above:
                return min(obs_above, key=lambda x: x.low)
        
        return matching_obs[-1] if matching_obs else None
    
    def _price_at_ob(self, current_price, bull_ob, bear_ob):
        tolerance = 0.0005
        
        if bull_ob and bull_ob.low <= current_price <= bull_ob.high + tolerance:
            return True, "BULLISH_OB"
        
        if bear_ob and bear_ob.low - tolerance <= current_price <= bear_ob.high:
            return True, "BEARISH_OB"
        
        return False, None
    
    def _nearest_fvg(self, fvgs, current_price, fvg_type):
        matching_fvgs = [f for f in fvgs if f.type == fvg_type and not f.filled]
        if not matching_fvgs:
            return None
        
        return min(matching_fvgs, key=lambda x: abs(x.midpoint - current_price))
    
    def _price_in_fvg(self, current_price, bull_fvg, bear_fvg):
        if bull_fvg and bull_fvg.low <= current_price <= bull_fvg.high:
            return True
        if bear_fvg and bear_fvg.low <= current_price <= bear_fvg.high:
            return True
        return False
    
    def _check_liquidity_sweep(self, liquidity, df_h1):
        if not liquidity:
            return False, None
        
        recent_highs = df_h1['high'].values[-5:]
        recent_lows = df_h1['low'].values[-5:]
        
        for liq in liquidity:
            if liq.swept:
                if liq.type == "BUY_SIDE":
                    if any(low < liq.price for low in recent_lows):
                        return True, "BUY"
                elif liq.type == "SELL_SIDE":
                    if any(high > liq.price for high in recent_highs):
                        return True, "SELL"
        
        return False, None
    
    def _detect_complete_smc(self, structure, at_ob, ob_type, in_fvg, swept, swept_dir, bull_ob, bear_ob):
        buy_score = 0
        sell_score = 0
        
        if structure.bos_type == "BULLISH" or (structure.choch_detected and structure.bias == "BEARISH"):
            buy_score += 25
        
        if at_ob and ob_type == "BULLISH_OB":
            buy_score += 35
        elif bull_ob and bull_ob.valid:
            buy_score += 15
        
        if in_fvg:
            buy_score += 20
        
        if swept and swept_dir == "BUY":
            buy_score += 20
        
        if structure.bos_type == "BEARISH" or (structure.choch_detected and structure.bias == "BULLISH"):
            sell_score += 25
        
        if at_ob and ob_type == "BEARISH_OB":
            sell_score += 35
        elif bear_ob and bear_ob.valid:
            sell_score += 15
        
        if in_fvg:
            sell_score += 20
        
        if swept and swept_dir == "SELL":
            sell_score += 20
        
        if buy_score >= 60:
            return True, "BUY", float(buy_score)
        elif sell_score >= 60:
            return True, "SELL", float(sell_score)
        
        if buy_score > sell_score:
            return False, "BUY", float(buy_score)
        elif sell_score > buy_score:
            return False, "SELL", float(sell_score)
        
        return False, None, 0.0
    
    def _calc_adx(self, highs, lows, closes, period=14):
        """Calculate ADX value and its slope (positive = rising)."""
        n = len(closes)
        if n < period * 2:
            return 0.0, 0.0
        
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)
        tr = np.zeros(n)
        
        for i in range(1, n):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
            minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0.0
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1]),
            )
        
        smoothed_tr = np.zeros(n)
        smoothed_plus = np.zeros(n)
        smoothed_minus = np.zeros(n)
        
        smoothed_tr[period] = np.sum(tr[1:period+1])
        smoothed_plus[period] = np.sum(plus_dm[1:period+1])
        smoothed_minus[period] = np.sum(minus_dm[1:period+1])
        
        for i in range(period + 1, n):
            smoothed_tr[i] = smoothed_tr[i-1] - smoothed_tr[i-1]/period + tr[i]
            smoothed_plus[i] = smoothed_plus[i-1] - smoothed_plus[i-1]/period + plus_dm[i]
            smoothed_minus[i] = smoothed_minus[i-1] - smoothed_minus[i-1]/period + minus_dm[i]
        
        dx = np.zeros(n)
        for i in range(period, n):
            if smoothed_tr[i] == 0:
                continue
            plus_di = 100 * smoothed_plus[i] / smoothed_tr[i]
            minus_di = 100 * smoothed_minus[i] / smoothed_tr[i]
            di_sum = plus_di + minus_di
            if di_sum > 0:
                dx[i] = 100 * abs(plus_di - minus_di) / di_sum
        
        adx = np.zeros(n)
        start = period * 2
        if start < n:
            adx[start] = np.mean(dx[period:start+1])
            for i in range(start + 1, n):
                adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
        
        adx_val = float(adx[-1])
        adx_slope = float(adx[-1] - adx[-5]) if n > 5 else 0.0
        return adx_val, adx_slope
    
    def _ema(self, data, period):
        ema = np.zeros(len(data))
        ema[0] = data[0]
        multiplier = 2 / (period + 1)
        
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        
        return ema
    
    def _log_context(self, ctx):
        logger.info(
            f"MarketContext {ctx.symbol}: "
            f"bias={ctx.structure.bias} "
            f"BOS={ctx.structure.bos_type} "
            f"AtOB={ctx.price_at_ob}({ctx.ob_type_at_price}) "
            f"InFVG={ctx.price_in_fvg} "
            f"LiqSwept={ctx.recent_liquidity_swept} "
            f"SMCSetup={ctx.complete_smc_setup}"
            f"({ctx.smc_setup_direction}:{ctx.smc_setup_score:.0f})"
        )
