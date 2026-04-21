import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. 终端风格配置 ---
st.set_page_config(page_title="NIQING | 智能雷达终端", layout="wide")
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #111418; border-right: 1px solid #30363d; }
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #d4af37, #f7e08b); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 缓存与数据抓取 (东财源) ---
@st.cache_data(ttl=60)
def fetch_em_spot():
    try:
        df = ak.stock_zh_a_spot_em()
        return df if not df.empty else None
    except:
        return None

def get_em_hist(symbol):
    try:
        # 增加极短延迟模拟真实用户，规避东财风控
        time.sleep(0.15)
        return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(30)
    except:
        return None

# --- 3. 左侧控制中心 (Sidebar) ---
with st.sidebar:
    st.title("妮情 · 智能雷达控制")
    st.divider()
    
    # 模块 1: 搜索
    st.subheader("🔍 个股搜索")
    search_code = st.text_input("输入代码 (如 600519)", key="side_search")
    
    st.divider()
    
    # 模块 2: 十字星
    st.subheader("🟢 阴线十字星预警")
    vol_star = st.number_input("准入额 (亿)", value=5.0)
    btn_star = st.button("开始全场扫描", key="btn_star")
    
    st.divider()
    
    # 模块 3: 金叉
    st.subheader("⚡ 金叉行情预警")
    vol_gold = st.number_input("活跃门槛 (亿)", value=8.0)
    btn_gold = st.button("开始深度计算", key="btn_gold")

# --- 4. 右侧结果展示区 (带动画反馈) ---
st.header("NIQING STUDIO · 监测大屏")

# A. 个股搜索反馈
if search_code:
    with st.status(f"🚀 正在透视个股: {search_code}...", expanded=True) as status:
        st.write("正在建立东财数据链路...")
        h_df = get_em_hist(search_code)
        if h_df is not None:
            st.write("数据同步完成，正在渲染K线图...")
            fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                            high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=400)
            st.plotly_chart(fig, use_container_width=True)
            status.update(label="✅ 搜索完成", state="complete", expanded=False)
        else:
            status.update(label="❌ 搜索失败，接口超时", state="error")

# B. 阴线十字星扫描动画
if btn_star:
    with st.status("🔍 正在执行全市场扫描...", expanded=True) as status:
        st.write("抓取东财实时快照...")
        spot = fetch_em_spot()
        if spot is not None:
            st.write("正在解构量能信号并计算形态...")
            spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
            pool = spot[spot['成交额'] >= vol_star * 100000000].copy()
            
            # 加入进度条动画
            progress_bar = st.progress(0)
            res = []
            for i, (idx, row) in enumerate(pool.iterrows()):
                # 更新进度条
                progress_bar.progress((i + 1) / len(pool))
                o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                if c < o and (h - l) > 0:
                    if (abs(o - c) / (h - l)) <= 0.12:
                        res.append({"代码": row['代码'], "名称": row['名称'], "最新价": c, "涨跌%": row['涨跌幅'], "量额(亿)": round(row['成交额']/1e8, 2)})
            
            if res:
                st.dataframe(pd.DataFrame(res), use_container_width=True)
            else:
                st.warning("暂无符合条件的信号")
            status.update(label="✅ 扫描任务结束", state="complete", expanded=False)
        else:
            status.update(label="❌ 接口繁忙，无法获取数据", state="error")

# C. 金叉深度计算动画
if btn_gold:
    with st.status("⚡ 正在进行活跃股金叉深度计算...", expanded=True) as status:
        st.write("提取活跃资金池...")
        spot = fetch_em_spot()
        if spot is not None:
            spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
            pool_gold = spot[spot['成交额'] >= vol_gold * 100000000].sort_values('成交额', ascending=False).head(30)
            
            # 进度动画
            gold_bar = st.progress(0)
            gold_res = []
            for i, (idx, row) in enumerate(pool_gold.iterrows()):
                st.write(f"计算中: {row['名称']} ({row['代码']})")
                gold_bar.progress((i + 1) / len(pool_gold))
                
                df_h = get_em_hist(row['代码'])
                if df_h is not None and len(df_h) >= 15:
                    low_9 = df_h['最低'].rolling(9).min()
                    high_9 = df_h['最高'].rolling(9).max()
                    rsv = (df_h['收盘'] - low_9) / (high_9 - low_9) * 100
                    k = rsv.ewm(com=2).mean()
                    d = k.ewm(com=2).mean()
                    j = 3 * k - 2 * d
                    if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
                        gold_res.append({"代码": row['代码'], "名称": row['名称'], "最新价": row['最新价'], "J值": round(j.iloc[-1],2)})
            
            if gold_res:
                st.dataframe(pd.DataFrame(gold_res), use_container_width=True)
            else:
                st.info("活跃池内暂无金叉信号")
            status.update(label="✅ 深度计算完成", state="complete", expanded=False)
        else:
            status.update(label="❌ 数据源异常", state="error")

# 缺省页
if not search_code and not btn_star and not btn_gold:
    st.info("👈 请在左侧侧边栏窗口进行操作。点击按钮后，此处将显示扫描动画。")
