import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="NIQING | 稳定版雷达", layout="wide")

# --- 2. 缓存机制：防止频繁请求导致被封 ---
@st.cache_data(ttl=60)  # 60秒内重复点击不会重新请求接口
def fetch_spot_data():
    try:
        df = ak.stock_zh_a_spot_em()
        if not df.empty:
            return df
    except:
        return pd.DataFrame()

def get_hist_data_safe(symbol):
    """带延迟的深度抓取，防止请求过快"""
    try:
        time.sleep(0.2) # 强制冷却 0.2 秒
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(30)
        return df
    except:
        return pd.DataFrame()

# --- 3. 左侧控制中心 (Sidebar) ---
with st.sidebar:
    st.title("妮情 · 策略控制")
    st.info("💡 提示：若报错，请点击右上方 'Clear Cache' 并等待1分钟。")
    
    # 窗口 1: 搜索窗口
    st.subheader("🔍 个股搜索")
    search_code = st.text_input("代码 (如 600519)", key="side_search")
    
    st.divider()
    
    # 窗口 2: 阴线十字星控制
    st.subheader("🟢 阴线十字星")
    vol_star = st.number_input("准入额 (亿)", value=5.0)
    strict_star = st.slider("实体占比", 0.05, 0.20, 0.12)
    btn_star = st.button("全场搜寻阴线")
    
    st.divider()
    
    # 窗口 3: 金叉预警控制
    st.subheader("⚡ 金叉行情")
    vol_gold = st.number_input("活跃门槛 (亿)", value=10.0) # 提高门槛减少请求
    btn_gold = st.button("全场搜寻金叉")

# --- 4. 右侧结果展示区 ---
st.header("NIQING STUDIO · 监测大屏")

# 4A: 个股搜索结果 (使用 Plotly 渲染)
if search_code:
    h_df = get_hist_data_safe(search_code)
    if not h_df.empty:
        fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                        high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
        fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("无法调取东财历史数据，请稍后再试。")

# 4B: 阴线十字星扫描
if btn_star:
    st.subheader("🟢 阴线十字星扫描结果")
    spot = fetch_spot_data()
    if not spot.empty:
        spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
        pool = spot[spot['成交额'] >= vol_star * 100000000].copy()
        res = []
        for _, row in pool.iterrows():
            o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
            if c < o and (h - l) > 0: # 必须是阴线
                if (abs(o - c) / (h - l)) <= strict_star:
                    res.append({"代码": row['代码'], "名称": row['名称'], "最新价": c, "涨跌%": row['涨跌幅'], "量额(亿)": round(row['成交额']/1e8, 2)})
        st.dataframe(pd.DataFrame(res), use_container_width=True)
    else:
        st.error("东财实时行情繁忙，请等待1分钟重试。")

# 4C: 金叉扫描 (限制请求总数以保稳定)
if btn_gold:
    st.subheader("⚡ 金叉扫描结果 (限前30活跃股)")
    spot = fetch_spot_data()
    if not spot.empty:
        spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
        # 限制只查前 30 名，绝对防止被封
        pool_gold = spot[spot['成交额'] >= vol_gold * 100000000].sort_values('成交额', ascending=False).head(30)
        gold_res = []
        for _, row in pool_gold.iterrows():
            df_h = get_hist_data_safe(row['代码'])
            if len(df_h) >= 15:
                low_9, high_9 = df_h['最低'].rolling(9).min(), df_h['最高'].rolling(9).max()
                rsv = (df_h['收盘'] - low_9) / (high_9 - low_9) * 100
                k, d = rsv.ewm(com=2).mean(), k.ewm(com=2).mean() # 此处修正计算逻辑
                j = 3 * k - 2 * d
                if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
                    gold_res.append({"代码": row['代码'], "名称": row['名称'], "最新价": row['最新价'], "J值": round(j.iloc[-1],2)})
        st.dataframe(pd.DataFrame(gold_res), use_container_width=True)
