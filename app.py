import streamlit as st
import akshare as ak
import pandas as pd
import time

# --- 1. 基础配置 ---
st.set_page_config(page_title="NIQING | 复合预警雷达", layout="wide")
st.title("妮情 · 量能 + 十字星 + 金叉 复合扫描终端")

if "c_list" not in st.session_state:
    st.session_state.c_list = pd.DataFrame()

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 预警配置")
    min_vol_亿 = st.number_input("最低成交额 (亿)", value=5.0)
    star_ratio = st.slider("十字星严格度 (实体占比)", 0.05, 0.25, 0.15)
    st.info("提示：若出现连接中断，请稍后再试。系统会自动重试数据采集。")

# --- 3. 核心计算函数 ---
def check_kdj_gold(df):
    """计算 KDJ 并判断今日是否金叉"""
    try:
        low_9 = df['low'].rolling(9).min()
        high_9 = df['high'].rolling(9).max()
        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
        k = rsv.ewm(com=2).mean()
        d = k.ewm(com=2).mean()
        j = 3 * k - 2 * d
        # 金叉：今日J上穿D
        if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
            return True, round(j.iloc[-1], 2)
        return False, 0
    except:
        return False, 0

def get_spot_data_safe():
    """带重试逻辑的实时行情抓取"""
    for _ in range(3):
        try:
            df = ak.stock_zh_a_spot_em()
            if not df.empty: return df
        except:
            time.sleep(1)
    return pd.DataFrame()

# --- 4. 扫描逻辑 ---
if st.button("🚀 启动全市场信号扫描"):
    with st.spinner("正在捕捉量量能信号..."):
        spot_df = get_spot_data_safe()
        if spot_df.empty:
            st.error("接口连接中断，请等待1-2分钟后重试。")
        else:
            spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')
            # 基础过滤
            pool = spot_df[spot_df['成交额'] >= min_vol_亿 * 100000000].copy()
            res = []
            
            for _, row in pool.iterrows():
                o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                # 计算十字星形态
                body = abs(o - c)
                amp = h - l
                if amp > 0 and (body / amp) <= star_ratio:
                    # 判断阴阳
                    star_type = "🔴 阳线十字" if c >= o else "🟢 阴线十字"
                    
                    # 针对符合形态的个股检测 KDJ
                    try:
                        hist = ak.stock_zh_a_hist(symbol=row['代码'], period="daily", adjust="qfq").tail(15)
                        is_gold, j_val = check_kdj_gold(hist)
                        if is_gold:
                            res.append({
                                "代码": row['代码'], "名称": row['名称'],
                                "形态": star_type, "预警": "⚡ KDJ金叉",
                                "J值": j_val, "最新价": c, "涨跌幅%": row['涨跌幅']
                            })
                    except: continue
            
            st.session_state.c_list = pd.DataFrame(res)
            st.success(f"扫描完毕，发现 {len(res)} 个符合条件的复合信号！")

# --- 5. 结果显示 ---
if not st.session_state.c_list.empty:
    # 样式渲染
    def highlight_type(val):
        color = '#ff4b4b' if '阳' in val else '#2ecc71'
        return f'color: {color}; font-weight: bold'
    
    st.dataframe(st.session_state.c_list.style.applymap(highlight_type, subset=['形态']), use_container_width=True)
else:
    st.info("等待扫描指令。")
