import streamlit as st
import random
import math
import copy
import collections
import os
import matplotlib.pyplot as plt

# ==========================================
# 1. 設定 & ユーティリティ & CSS
# ==========================================
MAX_TURNS = 12
MAX_HP = 100
INITIAL_ENERGY = 0

def get_valid_image_path(path):
    """画像パスの安全な取得"""
    if path and os.path.exists(path): return path
    if os.path.exists(f"image/{path}"): return f"image/{path}"
    if os.path.exists(f"item/{path}"): return f"item/{path}"
    if os.path.exists("placeholder.png"): return "placeholder.png"
    return None

def inject_custom_css():
    st.markdown("""
        <style>
        .stApp {
            background-color: white;
            background-image: radial-gradient(#333 1px, transparent 1px);
            background-size: 20px 20px;
        }
        .block-container {
            padding: 1rem;
        }


        /* 手札エリアの高さ固定 */
        .hand-box-container {
            min-height: 220px;
            display: flex;
            align-items: flex-start;
        }
        
        /* カード画像のホバー */
        .card-container {
            transition: transform 0.2s ease;
        }
        .card-container:hover {
            transform: scale(1.1);
            z-index: 100;
        }
        
        .stButton button { width: 100%; border-radius: 5px; font-weight: bold; }
        
        .score-box {
            text-align: center; color: black;
            text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
        }
        
        /* ドリンク画像 */
        .drink-image {
            margin-bottom: 5px;
            border-radius: 5px;
            overflow: hidden;
            height: 60px;
            display: flex;
            align-items: center; 
            justify-content: center;
        }
        .drink-image img {
            max-height: 100%; width: auto;
        }

        /* バフ数値の強調 */
        .buff-value-box {
            line-height:2.5; 
            font-weight:bold; 
            color:black; 
            background-color: #e0e0e0; 
            padding: 0 4px; 
            border-radius: 3px;
            text-align: center;
        }
        
        /* デッキ構築画面など */
        .deck-card-display {
            /* 背景色を少し明るく */
            background-color: rgba(55, 55, 60, 0.95);
            padding: 3px;
            margin-bottom: 10px;
            text-align: center;
        }
        /* カード名の文字色を明るい黄色に変更 */
        .deck-card-display h5 { 
            margin: 0; 
            font-size: 0.7rem; 
            color: #FFFF99; /* 明るい黄色 */
        }

        .deck-card-count { 
            font-size: 1.0rem; 
            font-weight: bold; 
            color: black; 
            margin-top: 5px; 
        }
        .deck-card-display img { max-width: 70%; height: auto; }
        .deck-list-item img { width: 100%; border-radius: 5px; }
        .deck-list-item {
            margin-bottom: 5px; 
            padding: 3px; 
            border-radius: 5px;
            border: 1px solid #444; 
            /* 背景色を少し明るく */
            background-color: rgba(70, 70, 75, 0.9); 
            color: black; 
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. クラス定義
# ==========================================
class Card:
    def __init__(self, name, cost_type, cost_value, card_type, effect_func, req_func=None, is_once=False, rarity='N', description="", image_path=None):
        self.name = name
        self.cost_type = cost_type
        self.cost_value = cost_value
        self.card_type = card_type
        self.effect_func = effect_func
        self.req_func = req_func
        self.is_once = is_once
        self.rarity = rarity
        self.description = description
        self.image_path = image_path if image_path else "placeholder.png"
    
    def can_use(self, state):
        if self.cost_type == 'conc' and state.concentration < self.cost_value: return False
        if self.cost_type == 'hp' and state.hp < self.cost_value: return False
        return self.req_func(state) if self.req_func else True

class PItem:
    def __init__(self, name, description, trigger_type, condition_func, effect_func, is_once=True, image_path=None):
        self.name = name
        self.description = description
        self.trigger_type = trigger_type
        self.condition_func = condition_func
        self.effect_func = effect_func
        self.is_once = is_once
        self.used = False
        self.image_path = image_path if image_path else "placeholder.png"
    
    def check(self, state):
        if self.is_once and self.used: return False
        if self.condition_func(state):
            self.effect_func(state)
            if self.is_once: self.used = True
            state.log(f"⭐ Pアイテム'{self.name}'が発動！")
            return True
        return False

class Drink:
    def __init__(self, name, description, effect_func, image_path=None):
        self.name = name
        self.description = description
        self.effect_func = effect_func
        self.image_path = image_path if image_path else "placeholder.png"

class Character:
    def __init__(self, name, genres, unique_card, unique_p_item, turn_events=None):
        self.name = name
        self.genres = genres
        self.unique_card = unique_card
        self.unique_p_item = unique_p_item
        self.turn_events = turn_events if turn_events else {}

class GameState:
    def __init__(self, character, deck, p_items, drinks=None, verbose=True):
        self.turn = 1
        self.max_turns = MAX_TURNS
        self.hp = MAX_HP
        self.energy = INITIAL_ENERGY
        self.score = 0
        self.score_gain_display = 0 
        
        self.verbose = verbose
        self.concentration = 0
        # buffsに param_boost_30 (30%固定強化) を追加
        self.buffs = {'good_condition': 0, 'super_good': 0, 'conc_boost': 0, 'param_boost': 0, 'param_boost_30': 0}
        self.buff_protection = {k: False for k in self.buffs}
        self.permanent_buffs = {'mental_conc': 0, 'active_conc': 0, 'active_score_fixed': 0, 'turn_end_conc': 0}
        
        self.double_charges = 0 
        self.double_next_mental_only = False
        self.summer_memory_active = False
        self.skill_use_count = 0
        self.last_card_type = None
        
        self.draw_reservations = collections.defaultdict(int)
        self.reserved_effects = collections.defaultdict(list)
        self.recurring_effects = []
        self.game_logs = []
        self.history = collections.defaultdict(list)

        self.deck = copy.deepcopy(deck)
        random.shuffle(self.deck)
        self.hand = []
        self.discard = []
        self.exile = []
        # キャラ固有アイテム + 選択アイテム
        self.p_items = [copy.deepcopy(p) for p in p_items]
        self.drinks = [copy.deepcopy(d) for d in drinks] if drinks else []
        self.turn_events = character.turn_events
        self.turn_info = self._generate_turn_schedule(character.genres)
        self.actions_remaining = 1
        self.next_turn_draw_bonus = 0

    def log(self, message):
        self.game_logs.append(message)

    def _generate_turn_schedule(self, preference):
        p1 = {'genre': preference[0], 'weight': 19.0, 'color': '#1f77b4'}
        p2 = {'genre': preference[1], 'weight': 14.0, 'color': '#ffcc00'}
        p3 = {'genre': preference[2], 'weight': 8.0,  'color': '#d62728'}
        schedule = [None] * 12
        schedule[0] = p1; schedule[11] = p1
        schedule[9] = p3; schedule[10] = p2
        pool = [p1]*4 + [p2]*3 + [p3]*1
        random.shuffle(pool)
        for i in range(12):
            if schedule[i] is None: schedule[i] = pool.pop()
        return schedule

    def draw_cards(self, num):
        MAX_HAND_SIZE = 5
        for _ in range(num):
            if len(self.hand) >= MAX_HAND_SIZE: break
            if not self.deck:
                if not self.discard: break
                self.deck = self.discard[:]
                self.discard = []
                random.shuffle(self.deck)
            if self.deck:
                self.hand.append(self.deck.pop())

    def calculate_score(self, base, conc_rate=1.0):
        # param_boost (1つ10%) と param_boost_30 (固定30%) を計算
        # ブーストエキス: 30%固定がONなら +0.3
        # センブリなど: param_boost * 0.1
        boost_mult = 1.0 + (self.buffs['param_boost'] * 0.1)
        if self.buffs['param_boost_30'] > 0:
            boost_mult += 0.3
            
        added_conc = self.concentration * conc_rate
        power = (base + added_conc) * boost_mult
        power = math.ceil(power)
        
        mult = 1.0
        if self.buffs['good_condition'] > 0:
            mult = 1.5
            if self.buffs['super_good'] > 0:
                mult += self.buffs['good_condition'] * 0.1
        genre_w = self.turn_info[self.turn-1]['weight']
        score = math.ceil(power * mult * genre_w)
        
        self.score += score
        self.score_gain_display += score
        self.log(f"🎤 Score +{score}")

    def start_turn(self):
        self.game_logs = []
        self.score_gain_display = 0
        if self.turn in self.turn_events: self.turn_events[self.turn](self)
        self.actions_remaining = 1
        for p in self.p_items:
            if p.trigger_type == 'turn_start': p.check(self)
        for k, v in self.buffs.items(): self.buff_protection[k] = (v == 0)
        
        reserved = self.draw_reservations[self.turn] + self.next_turn_draw_bonus
        self.next_turn_draw_bonus = 0
        draw_num = 3 + reserved - len(self.hand)
        if draw_num > 0: self.draw_cards(draw_num)
        
        active_recurring = []
        for eff in self.recurring_effects:
            eff['func'](self)
            eff['turns'] -= 1
            if eff['turns'] > 0: active_recurring.append(eff)
        self.recurring_effects = active_recurring

    def play_card(self, idx):
        self.score_gain_display = 0
        if self.actions_remaining <= 0 or not (0 <= idx < len(self.hand)): return False
        card = self.hand[idx]
        if not card.can_use(self): return False

        self.hand.pop(idx)
        self.history[self.turn].append(card.name)
        self.last_card_type = card.card_type

        if card.cost_type == 'conc':
            self.concentration -= card.cost_value
        else:
            actual = card.cost_value
            if self.energy >= actual:
                self.energy -= actual
            else:
                remain = actual - self.energy
                self.energy = 0
                self.hp = max(0, self.hp - remain)
        
        if card.card_type == 'mental' and self.permanent_buffs['mental_conc'] > 0:
            self.concentration += math.ceil(self.permanent_buffs['mental_conc'] * (1.5 if self.buffs['conc_boost']>0 else 1.0))
        if card.card_type == 'active' and self.permanent_buffs['active_conc'] > 0:
            self.concentration += math.ceil(self.permanent_buffs['active_conc'] * (1.5 if self.buffs['conc_boost']>0 else 1.0))

        repeats = 1
        if self.double_charges > 0:
            repeats = 2
            self.double_charges -= 1
            self.log(f"🔄 '{card.name}'の効果が2回発動！")
        elif self.double_next_mental_only and card.card_type == 'mental':
            repeats = 2
            self.double_next_mental_only = False
            self.log(f"🔄 メンタル再演！'{card.name}'が2回発動！")

        for _ in range(repeats):
            if card.card_type == 'active':
                if card.name == "至高のエンタメ":
                    # 至高のエンタメ自身は得点化しない（ただ effect_func は repeats 回実行して
                    # permanent_buffs['active_score_fixed'] を加算する）
                    card.effect_func(self)
                else:
                    # 現在の固定P合計を取得（存在しなければ0）
                    total_fixed = self.permanent_buffs.get('active_score_fixed', 0)

                    # 「3単位」で蓄積されている想定（至高のエンタメは +3 を add_permanent_buff する実装）
                    unit = 3
                    if total_fixed > 0:
                        # count 回に分けて個別に得点計算する
                        count = total_fixed // unit
                        remainder = total_fixed % unit

                        for i in range(count):
                            # 個別に calculate_score(3) を呼ぶ（非線形効果を分割して得点化）
                            self.calculate_score(unit)

                    # その後カード固有効果を実行（コール＆レスポンス等）
                    card.effect_func(self)
            else:
                # メンタル等は従来どおり（active 固定P は関係ない）
                card.effect_func(self)

        if card.is_once: self.exile.append(card)
        else: self.discard.append(card)

        if self.summer_memory_active:
            self.skill_use_count += 1
            if self.skill_use_count % 5 == 0: self.calculate_score(4)
        
        for p in self.p_items:
            if p.trigger_type == 'after_action': p.check(self)

        self.actions_remaining -= 1
        return True

    def use_drink(self, idx):
        self.score_gain_display = 0
        if 0 <= idx < len(self.drinks):
            drink = self.drinks.pop(idx)
            self.log(f"🥤 {drink.name}を使用")
            drink.effect_func(self)
            return True
        return False

    def end_turn(self):
        self.score_gain_display = 0
        if self.is_game_over(): return
        if self.permanent_buffs['turn_end_conc'] > 0:
            self.concentration += math.ceil(self.permanent_buffs['turn_end_conc'] * (1.5 if self.buffs['conc_boost']>0 else 1.0))
        for k in self.buffs:
            if self.buffs[k] > 0 and not self.buff_protection[k]: self.buffs[k] -= 1
        
        self.discard.extend(self.hand)
        self.hand = []
        self.turn += 1
        for func in self.reserved_effects[self.turn]: func(self)

    def is_game_over(self):
        return self.turn > self.max_turns

    def add_permanent_buff(self, type, val):
        if type in self.permanent_buffs: self.permanent_buffs[type] += val
    def add_concentration(self, amount):
        mult = 1.5 if self.buffs['conc_boost'] > 0 else 1.0
        self.concentration += math.ceil(amount * mult)
    def add_buff(self, key, turns):
        if self.buffs[key] == 0: self.buff_protection[key] = True
        self.buffs[key] += turns
    def reserve_draw(self, turns_later, amount):
        if self.turn + turns_later <= self.max_turns: self.draw_reservations[self.turn + turns_later] += amount
    def reserve_effect(self, turns_later, func, desc=""):
        if self.turn + turns_later <= self.max_turns: self.reserved_effects[self.turn + turns_later].append(func)
    def add_recurring_effect(self, turns, func, desc="継続効果"):
        self.recurring_effects.append({'turns': turns, 'func': func, 'desc': desc})

# ==========================================
# 3. データ生成 (カード、アイテム、ドリンク)
# ==========================================
def get_full_card_pool():
    pool = []
    
    # SSR
    def eff_famous_idol(s): s.double_charges += 1; s.actions_remaining += 1; s.add_buff('good_condition', -1)
    pool.append(Card("国民的アイドル", 'hp', 0, 'mental', eff_famous_idol, is_once=True, rarity='SSR',description="[1回] 次の効果を2回発動(重複可)/行動+1", image_path="famous_idle.png"))
    def eff_call_response(s): s.calculate_score(15); s.calculate_score(34, conc_rate=1.5)
    pool.append(Card("コール＆レスポンス+", 'hp', 3, 'active', eff_call_response, is_once=True, rarity='SSR',description="P+15/P+34(集中1.5倍)", image_path="card_cr.png"))
    def eff_shikiri(s): ct=len(s.hand); s.discard.extend(s.hand); s.hand=[]; s.draw_cards(ct+2); s.actions_remaining+=1
    pool.append(Card("仕切り直し", 'hp', 2, 'mental', eff_shikiri, is_once=True, rarity='SSR',description="[1回] 手札入替+2枚/行動+1", image_path="card_shikiri.png"))
    def eff_turn_end_boost(s): s.add_permanent_buff('turn_end_conc', 2)
    pool.append(Card("天真爛漫", 'hp', 4, 'mental', eff_turn_end_boost, is_once=True, rarity='SR',description="永続:ターン終了時集中+2", image_path="card_ranman.png"))
    def cond_hitotoki(s): return s.turn>=3
    def eff_hitotoki(s): s.add_buff('good_condition',-1); s.add_buff('conc_boost',3); s.add_concentration(4)
    pool.append(Card("ほぐれるひととき", 'hp', 0, 'mental', eff_hitotoki, req_func=cond_hitotoki, is_once=True, rarity='SSR',description="[3T以降]集中+50%/集中+4", image_path="card_hogure.png"))
    def eff_shisen(s): s.add_buff('super_good',5); s.actions_remaining+=1
    pool.append(Card("魅惑の視線", 'conc', 3, 'mental', eff_shisen, is_once=True, rarity='SSR',description="絶好調+5/行動+1", image_path="card_shisen.png"))
    def eff_entertainment(s): s.reserve_draw(1,1); s.add_permanent_buff('active_score_fixed', 3)
    pool.append(Card("至高のエンタメ", 'conc', 2, "active", eff_entertainment, is_once=True, rarity='SSR',description="永続:アクティブP+3/次T1枚", image_path="card_entame.png"))
    def eff_paformance(s): s.add_buff('super_good',4); s.reserve_effect(1,lambda x:x.calculate_score(47)); s.reserve_effect(2,lambda x:x.calculate_score(21,conc_rate=1.0))
    pool.append(Card("魅惑のパフォーマンス", 'hp', 6, 'active', eff_paformance, is_once=True,rarity='SSR', description="絶好調+4/1T後P+47/2T後P+21", image_path="card_pafo.png"))
    def eff_summer_memory(s): s.actions_remaining+=1; s.summer_memory_active=True
    pool.append(Card("夏夜に咲く思い出", 'hp', 6, 'active', eff_summer_memory, is_once=True, rarity='SSR',description="行動+1/5回毎にP+4", image_path="card_natsuyo.png"))
    def eff_tenpu(s): s.add_buff('good_condition',6); s.add_concentration(3); s.reserve_effect(1,lambda x:setattr(x,'actions_remaining',x.actions_remaining+1))
    pool.append(Card("天賦の才", 'hp', 5, 'mental', eff_tenpu, is_once=True, rarity='SSR', description="好調+6/集中+3/次行動+1", image_path="card_tenpu.png"))
    def eff_syuki(s): s.add_permanent_buff('mental_conc', 2); s.add_concentration(1)
    pool.append(Card("自己肯定感爆上げ中", 'hp', -1, 'mental', eff_syuki, is_once=True, rarity='SSR',description="永続:メンタル集中+2", image_path="card_syuki.png"))

    # SR
    def eff_prey_power(s): s.add_permanent_buff('active_conc', 1); s.add_concentration(2)
    pool.append(Card("願いの力", 'hp', 3, 'mental', eff_prey_power, is_once=True, rarity='SR',description="永続:アクティブ使用時集中+1/集中+2", image_path="card_negai.png"))
    def eff_spot_light(s): s.reserve_draw(1,2); s.reserve_draw(2,1); s.add_buff('good_condition',9)
    pool.append(Card("スポットライト", 'hp', 0, 'mental', eff_spot_light, rarity='SR',description="1T後2枚+2T後1枚/好調+9", image_path="card_spot.png"))
    def eff_shupure(s): s.calculate_score(6); s.add_buff('good_condition', 3); s.actions_remaining+=1
    pool.append(Card("シュプレヒコール", 'conc', 1, 'active', eff_shupure, rarity='SR',description="[集中1] P+6/好調3T/行動+1", image_path="card_syupu.png"))
    def eff_exist(s): s.add_concentration(5); s.actions_remaining+=1
    pool.append(Card("存在感", 'hp', 0, 'mental', eff_exist, rarity='SR',description="集中+5/行動+1", image_path="card_sonzai.png"))
    def eff_im_idol(s): s.draw_cards(2); s.actions_remaining+=1
    pool.append(Card("アイドル宣言", 'hp', 0, 'mental', eff_im_idol,is_once=True,rarity='SR',description="２枚引く", image_path="card_dolsen.png"))
    def eff_aizu(s): s.add_buff('good_condition', 7)
    pool.append(Card("始まりの合図+", 'hp', 3, 'mental', eff_aizu, is_once=True, rarity='SR',description="[1回] 好調+7", image_path="card_aizu.png")) 

    # R
    def eff_hitokyu(s): 
        s.add_buff('good_condition', 4)
        s.add_concentration(5)
    pool.append(Card("ひと呼吸+", 'hp', 7, 'mental', eff_hitokyu, is_once=True, rarity='R',description="[1回] 好調+4/集中+5", image_path="card_hitokyu.png")) 

    card_dict = {card.name: card for card in pool}
    return card_dict

def get_all_p_items():
    items = []
    items.append(PItem("しゅきハート+", "メンタル(集中13↑)", "after_action", 
                       lambda s: s.last_card_type=='mental' and s.concentration>=13, 
                       lambda s: [setattr(s,'energy',s.energy+10),setattr(s, 'double_next_mental_only', True), s.draw_cards(2), setattr(s,'actions_remaining',s.actions_remaining+1)], 
                       is_once=True, image_path="item_syuki_heart.png"))
    items.append(PItem("大荷物", "ダンス時行動+1", "turn_start", 
                       lambda s: s.turn_info[s.turn-1]['genre']=='dance', 
                       lambda s: setattr(s,'actions_remaining',s.actions_remaining+1), 
                       is_once=True, image_path="item_hako.png"))
    items.append(PItem("きっかけ", "ビジュアル時行動+1", "turn_start", 
                       lambda s: s.turn_info[s.turn-1]['genre']=='visual', 
                       lambda s: setattr(s,'actions_remaining',s.actions_remaining+1), 
                       is_once=True, image_path="item_nakanaori.png"))
    items.append(PItem("Tシャツ", "好調時行動+1", "turn_start", 
                       lambda s: s.buffs['good_condition']>0, 
                       lambda s: [setattr(s,'actions_remaining',s.actions_remaining+1), s.add_buff('good_condition',6)], 
                       is_once=True, image_path="item_shirt.png"))
    return {item.name: item for item in items}

def get_all_drinks():
    drinks = []
    def eff_senburi(s): 
        s.add_buff('param_boost',5); s.draw_cards(2); s.add_recurring_effect(5, lambda x:x.draw_cards(1), desc="ドロー継続")
    drinks.append(Drink("センブリソーダ", "P上昇+10%/2枚引く/5T継続ドロー", eff_senburi, image_path="drink_senburi.png"))
    
    # ★修正: ブーストエキスは「固定30%上昇」の効果に変更 (値は減らない、ターンのみ減る)
    # 実装: buffs['param_boost_30'] に継続ターンを設定
    def eff_boost(s): 
        s.hp-=2
        s.add_buff('param_boost_30', 3) # 3ターン継続
    drinks.append(Drink("ブーストエキス", "HP-2/P上昇30%(3T)", eff_boost, image_path="drink_boost.png"))
    
    return {d.name: d for d in drinks}

# ★キャラクター定義
def get_characters():
    card_pool = get_full_card_pool()
    item_pool = get_all_p_items()
    
    turn_evs = { 5: lambda s: s.add_concentration(8), 9: lambda s: s.add_concentration(13) }
    
    chars = {}
    chars['shuki_kotone'] = Character(
        "しゅきことね", 
        ['dance', 'visual', 'vocal'], 
        card_pool.get("自己肯定感爆上げ中"), 
        item_pool.get("しゅきハート+"),
        turn_events=turn_evs
    )
    # 必要に応じて他キャラ追加
    return chars

# ★テンプレデッキ
def get_template_decks():
    # とりあえずシンプルな構成
    return {
        "理想": {
            "国民的アイドル": 1, "コール＆レスポンス+": 1, "仕切り直し": 1, "魅惑の視線": 1,
            "至高のエンタメ": 1, "魅惑のパフォーマンス": 1, "夏夜に咲く思い出": 1, "天賦の才": 1,
            "シュプレヒコール": 1, "ひと呼吸+": 1,"ほぐれるひととき":1,"願いの力":1,"アイドル宣言":1,
            "存在感":1,"スポットライト":1,"天真爛漫":1,"始まりの合図+":1,"夏夜に咲く思い出":1
        }
    }

# ==========================================
# 4. UI描画 (ドーナツグラフ)
# ==========================================
def draw_turn_circle(state):
    sizes = [1] * 12
    colors = []
    for i in range(12):
        if i < state.turn - 1:
            colors.append('#222222')
        else:
            colors.append(state.turn_info[i]['color'])
    explode = [0.0] * 12
    if state.turn <= 12:
        explode[state.turn - 1] = 0.15
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.pie(sizes, colors=colors, startangle=90, counterclock=True, 
           wedgeprops=dict(width=0.4, edgecolor='#444'), explode=explode)
    turn_text = f"{13-state.turn}" if state.turn <= 12 else "END"
    ax.text(0, 0, turn_text, ha='center', va='center', fontsize=24, fontweight='bold', color='black')
    fig.patch.set_alpha(0.0)
    ax.axis('equal')
    return fig

# ==========================================
# 5. メインアプリ
# ==========================================
def init_game():
    st.session_state.game_state = 'setup'
    st.session_state.full_card_pool = get_full_card_pool()
    st.session_state.all_items = get_all_p_items()
    st.session_state.all_drinks = get_all_drinks()
    st.session_state.characters = get_characters()
    st.session_state.deck_list = {} # {name: count}
    
    # 初期選択状態
    st.session_state.selected_char_key = 'shuki_kotone'
    st.session_state.selected_items = []
    st.session_state.selected_drinks = []

def start_game():
    char = st.session_state.characters[st.session_state.selected_char_key]
    
    # デッキ構築: 選択カード + キャラ固有カード
    deck = []
    for card_name, count in st.session_state.deck_list.items():
        card = st.session_state.full_card_pool.get(card_name)
        if card:
            deck.extend([copy.deepcopy(card) for _ in range(count)])
    if char.unique_card:
        deck.append(copy.deepcopy(char.unique_card))
    
    # アイテム構築: 選択アイテム + キャラ固有アイテム
    p_items = []
    if char.unique_p_item:
        p_items.append(copy.deepcopy(char.unique_p_item))
    for item_name in st.session_state.selected_items:
        item = st.session_state.all_items.get(item_name)
        if item:
            p_items.append(copy.deepcopy(item))
            
    # ドリンク構築
    drinks = []
    for drink_name in st.session_state.selected_drinks:
        d = st.session_state.all_drinks.get(drink_name)
        if d:
            drinks.append(copy.deepcopy(d))
            
    st.session_state.game = GameState(char, deck, p_items, drinks=drinks, verbose=True)
    st.session_state.game.start_turn()
    st.session_state.game_state = 'playing'
    st.rerun()

def setup_screen():
    st.title("キャラ・デッキ構築画面")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("1. キャラクター選択")
        char_options = list(st.session_state.characters.keys())
        # 表示名をマッピング
        char_names = {k: v.name for k, v in st.session_state.characters.items()}
        selected = st.radio("キャラクター", char_options, format_func=lambda x: char_names[x])
        st.session_state.selected_char_key = selected
        
        char = st.session_state.characters[selected]
        st.info(f"固有カード: {char.unique_card.name}\n\n固有アイテム: {char.unique_p_item.name}")

        st.markdown("---")
        st.subheader("2. Pアイテム選択")
        # 固有アイテム以外を選択可能にする
        available_items = [name for name in st.session_state.all_items.keys() if name != char.unique_p_item.name]
        st.session_state.selected_items = st.multiselect("アイテムを追加", available_items)
        
        st.markdown("---")
        st.subheader("3. ドリンク選択 (最大3つ)")
        
        # 「(なし)」を選択肢の先頭に追加
        available_drinks = ["(なし)"] + list(st.session_state.all_drinks.keys())
        
        # 現在の選択状態を一時リストに保持
        current_selection = st.session_state.selected_drinks
        new_selection = []

        cols = st.columns(3)
        for i in range(3):
            with cols[i]:
                # デフォルト値を決定 (現在の選択があればそれを、なければ "なし")
                default_val = current_selection[i] if i < len(current_selection) else "(なし)"
                
                # リストに存在しないアイテムが指定されていた場合のエラー回避
                if default_val not in available_drinks:
                    default_val = "(なし)"

                # セレクトボックスを表示 (重複選択可能になる)
                selected = st.selectbox(
                    f"枠 {i+1}", 
                    available_drinks, 
                    index=available_drinks.index(default_val),
                    key=f"drink_slot_{i}"
                )
                
                if selected != "(なし)":
                    new_selection.append(selected)

        # セッションステートを更新
        st.session_state.selected_drinks = new_selection

    with col2:
        st.subheader("4. デッキ構築")
        
        # テンプレート読み込み機能
        templates = get_template_decks()
        c_temp, c_btn = st.columns([3, 1])
        selected_template = c_temp.selectbox("テンプレートから読み込む", ["(選択なし)"] + list(templates.keys()))
        if c_btn.button("読込"):
            if selected_template in templates:
                st.session_state.deck_list = templates[selected_template].copy()
                st.rerun()
        
        # 現在のデッキ表示 & 編集
        deck_list = st.session_state.deck_list
        card_pool = st.session_state.full_card_pool
        
        st.markdown(f"**現在の枚数:** <span class='deck-card-count'>{sum(deck_list.values())}</span> (固有カード除く)", unsafe_allow_html=True)
        
        # 選択済みカードリスト
        if deck_list:
            sorted_deck = sorted(deck_list.items())
            d_cols = st.columns(7)
            idx = 0
            for name, count in sorted_deck:
                if count > 0:
                    with d_cols[idx % 5]:
                        card = card_pool[name]
                        st.caption(f"{name}")
                        cc1, cc2 = st.columns([1, 1])
                        cc1.write(f"x{count}")
                        if cc2.button("➖", key=f"del_{name}"):
                            deck_list[name] -= 1
                            if deck_list[name] <= 0: del deck_list[name]
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    idx += 1
        else:
            st.caption("カードが選択されていません")

        st.markdown("---")
        st.write("▼ カードプールから追加")
        pool_items = list(card_pool.values())
        # レアリティ順ソート
        pool_items.sort(key=lambda c: ({'SSR':0, 'SR':1, 'R':2, 'N':3}.get(c.rarity, 9), c.name))
        
        p_cols = st.columns(9)
        display_idx = 0
        for i, card in enumerate(pool_items):
            # キャラ固有カードはプールから除外（自動追加されるため）
            if card.name == char.unique_card.name:
                continue
                
            with p_cols[display_idx % 8]:

                # 画像
                st.image(get_valid_image_path(card.image_path) , width=100)
                # 名前とレアリティ
                r_color = {'SSR':'#FF0000', 'SR':'#3311BB', 'R':'#4CAF50'}.get(card.rarity, 'white')
                st.markdown(f"<div style='font-size:1rem; color:{r_color}; white-space:nowrap; overflow:hidden;'>{card.name}</div>", unsafe_allow_html=True)
                
                if st.button("➕", key=f"add_{card.name}"):
                    deck_list[card.name] = deck_list.get(card.name, 0) + 1
                    st.rerun()

            display_idx += 1

    st.markdown("---")
    # 開始ボタン
    total_cards = sum(deck_list.values()) + 1 # +1は固有カード分
    if st.button("ゲーム開始", type="primary", use_container_width=True, disabled=(total_cards < 1)):
        start_game()

def game_playing_screen(s):
    col_L, col_sep1, col_C, col_sep2, col_R = st.columns([1.0, 0.3, 4, 0.3, 1.5])

    with col_sep1:
        st.markdown("<div style='width:100%; height:100%; border-right:1px solid #ccc;'></div>", unsafe_allow_html=True)

    with col_sep2:
        st.markdown("<div style='width:100%; height:100%; border-right:1px solid #ccc;'></div>", unsafe_allow_html=True)

    # ================= 左カラム =================
    with col_L:
        # 1. ターン円グラフ
        if s.turn <= 12:
            info = s.turn_info[s.turn-1] 
            genre_map = {'dance': 'Dance', 'visual': 'Visual', 'vocal': 'Vocal'}
            st.pyplot(draw_turn_circle(s), use_container_width=True)
            st.markdown(f"<div style='text-align:center; font-weight:bold; color:{info['color']}'>{genre_map[info['genre']]}<br>{int(info['weight']*100)}%</div>", unsafe_allow_html=True)
        else:
            st.write("終了")

        st.markdown("---")

        # 2. バフ情報
        
        def show_buff_with_icon(label, val, icon_path):
            c1, c2 = st.columns([1, 1.5])
            with c1: st.image(get_valid_image_path(icon_path), use_container_width=True)
            with c2: st.markdown(f"<div class='buff-value-box'>{val}</div>", unsafe_allow_html=True)

        show_buff_with_icon("集中", s.concentration, "conc_icon.png")
        if s.buffs['good_condition'] > 0:
            show_buff_with_icon("好調", s.buffs['good_condition'], "good_icon.png")
        if s.buffs['super_good'] > 0:
            show_buff_with_icon("絶好調", s.buffs['super_good'], "super_good_icon.png")
        
        if s.double_charges > 0:
            st.markdown(f"<div style='color:#FFD700; font-weight:bold; text-align:center; margin-top:5px;'>🔄 再演: {s.double_charges}</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.caption("継続効果")
        
        def buff_text_row(label, val):
            st.markdown(f"""
            <div style='display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:2px;'>
                <span>{label}</span>
                <span style='font-weight:bold; background-color:#e0e0e0; color:black; padding:0 4px; border-radius:3px;'>{val}</span>
            </div>
            """, unsafe_allow_html=True)

        if s.buffs['param_boost'] > 0:
             buff_text_row("P上昇(10%)", f"+{s.buffs['param_boost']*10}%")
        
        if s.buffs['param_boost_30'] > 0:
             buff_text_row("P上昇(30%)", f"{s.buffs['param_boost_30']}T")

        if s.recurring_effects:
            for eff in s.recurring_effects:
                desc = eff.get('desc', '効果')
                buff_text_row(desc, f"{eff['turns']}T")
        elif s.buffs['param_boost'] == 0 and s.buffs['param_boost_30'] == 0:
            st.caption("(なし)")

        st.markdown("---")

        def show_card_grid(cards, key_prefix):
            if not cards:
                st.caption("なし")
                return
            cols = st.columns(3)
            for i, card in enumerate(cards):
                with cols[i % 3]:
                    st.image(get_valid_image_path(card.image_path), use_container_width=True)

        with st.expander(f"山札 ({len(s.deck)})"):
            show_card_grid(s.deck, "deck")
            
        with st.expander(f"捨て札 ({len(s.discard)})"):
            show_card_grid(s.discard, "discard")

        with st.expander(f"除外 ({len(s.exile)})"):
            show_card_grid(s.exile, "exile")


    # ================= 中央カラム =================
    with col_C:

        # ----- 1. スコア表示 -----
        with st.container():
            st.markdown("---")
            gain = s.score_gain_display
            gain_txt = f"<span style='color:black; font-size:1.5rem; margin-left:10px;'>(+{gain:,})</span>" if gain > 0 else ""
            st.markdown(f"<div class='score-box'><span style='font-size:3.5rem; font-weight:bold'>{s.score:,}</span>{gain_txt}</div>", unsafe_allow_html=True)
            st.markdown("---")
            st.metric("行動数", s.actions_remaining)

        # ----- 2. 手札エリア -----
        with st.container():

            if not s.hand:
                st.info("手札がありません")
            else:
                h_cols = st.columns(5)
                for i in range(5):
                    with h_cols[i]:
                        if i < len(s.hand):
                            card = s.hand[i]
                            can_use = card.can_use(s) and s.actions_remaining > 0
                                
                            st.markdown('<div class="card-container">', unsafe_allow_html=True)
                            st.image(get_valid_image_path(card.image_path), use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                                
                            tooltip = f"【{card.name}】\n{card.description}\nコスト: {card.cost_value}"
                            if st.button("使用", key=f"cd_{s.turn}_{i}", disabled=not can_use, help=tooltip):
                                if s.play_card(i):
                                    st.rerun()
                        else:
                            st.write("") 
            st.markdown("---")

        # ----- 3. ドリンクエリア -----
        with st.container():
            st.caption("Drinks")
            d_cols = st.columns(3)
            for i in range(3):
                with d_cols[i]:
                    if i < len(s.drinks):
                        d = s.drinks[i]
                        st.markdown('<div class="drink-image">', unsafe_allow_html=True)
                        st.image(get_valid_image_path(d.image_path), use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                        if st.button(f"{d.name}", key=f"dr_btn_{i}", help=d.description):
                            s.use_drink(i)
                            st.rerun()
                    else:
                        st.markdown("<div style='height:60px; display:flex; align-items:center; justify-content:center; color:#555;'>Empty</div>", unsafe_allow_html=True)


    # ================= 右カラム =================
    with col_R:
        # 1. ステータス & ターン終了
        st.metric("元気", s.energy)
        st.write(f"体力 {s.hp}/{MAX_HP}")
        st.progress(min(s.hp/MAX_HP, 1.0))
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("ターン終了", type="primary", use_container_width=True):
            s.end_turn()
            s.start_turn()
            st.rerun()


        # 2. Pアイテム
        st.caption("Pアイテム")
        for p in s.p_items:
            pc1, pc2 = st.columns([1, 2])
            with pc1:
                st.image(get_valid_image_path(p.image_path), use_container_width=True)
            with pc2:
                label = f"{p.name}(済)" if p.used else f"{p.name}"
                if st.button(label, key=f"pitem_{p.name}", help=p.description):
                    status = "発動済み" if p.used else "未発動"
                    st.toast(f"【{p.name}】\n{p.description}\n状態: {status}")

        # 3. ログ
        with st.expander("ログ"):
            for l in reversed(s.game_logs):
                st.caption(l)

    # 終了判定
    if s.is_game_over():
        st.session_state.game_state = 'result'
        st.rerun() 

def get_rank(score):
    base = 9957
    exam = 1500 + 750 + 800 + 400 + 0.01* (score - 40000)
    return math.ceil(base + exam)

def result_screen(s):
    rank = get_rank(s.score)

    # ---- 中央寄せレイアウト ----
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div style='height:120px;'></div>", unsafe_allow_html=True)

        # スコア（でかい文字）
        st.markdown(f"""
        <div style='text-align: center; font-size: 32px; font-weight: bold;'>
            Score: {s.score:,}
        </div>
        """, unsafe_allow_html=True)

        # ランク（もっとでかく）
        st.markdown(f"""
        <div style='text-align: center; font-size: 48px; font-weight: bold; color:#FFAA00;'>
            Rank: {rank}
        </div>
        """, unsafe_allow_html=True)

        # 画像（任意、使わなければ消してOK）
        # st.image("images/result_rank.png", use_column_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Restart ボタンも中央に置く
        if st.button("🔄 Restart"):
            init_game()
            st.rerun()

def main_app():
    st.set_page_config(layout="wide", page_title="Idol", initial_sidebar_state="collapsed")
    inject_custom_css()
    
    if 'game_state' not in st.session_state:
        init_game()

    if st.session_state.game_state == 'setup':
        setup_screen()
    elif st.session_state.game_state == 'playing':
        s = st.session_state.game
        game_playing_screen(s)
    elif st.session_state.game_state == 'result':
        s = st.session_state.game
        result_screen(s)

if __name__ == "__main__":
    main_app()