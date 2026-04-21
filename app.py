import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. 界面与风格 ---
st.set_page_config(page_title="NIQING | 多源抗压终端", layout="wide")
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #0e1117; border-right: 1px solid #d4af37; }
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #d4af37, #f7e08b); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 多源数据抓取逻辑 ---
def get_market_snapshot():
    """多源切换：东财 -> 新浪 -> 腾讯"""
    sources = [
        ("东方财富", ak.stock_zh_a_spot_em),
        ("新浪财经", ak.stock_zh_a_spot_sina)
    ]
    for name, func in sources:
        try:
            df = func()
            if df is not None and not df.empty:
                return df, name
        except:
            continue
    return None, None

def get_hist_with_retry(symbol):
    """抓取历史K线，失败后尝试备用接口"""
    time.sleep(0.2) # 基础冷却
    try:
        # 首选东财历史源
        return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(45)
    except:
        try:
            # 备选新浪源
            return ak.stock_zh_a_daily_qfq(symbol="sh" + symbol if symbol.startswith('6') else "sz" + symbol).tail(45)
        except:
            return None

# --- 3. 左侧控制中心 ---
with st.sidebar:
    st.title("妮情 · 策略中心")
    st.divider()
    
    # 窗口 1: 个股搜索
    st.subheader("🔍 个股搜索")
    target_code = st.text_input("代码 (如 600519)", key="input_target")
    
    st.divider()
    
    # 窗口 2 & 3: 全局扫描控制
    st.subheader("📡 全局信号监控")
    vol_limit = st.number_input("准入成交额 (亿)", value=5.0)
    btn_scan = st.button("🚀 启动全场扫描", key="main_scan")
    
    st.divider()
    if st.button("♻️ 重置所有连接"):
        st.cache_data.clear()
        st.rerun()

# --- 4. 右侧结果大屏 ---
st.header("NIQING STUDIO · 多源监测大屏")

# --- 顶部：个股详情窗口 ---
if target_code:
    with st.status(f"正在建立链路透视: {target_code}...") as status:
        h_df = get_hist_with_retry(target_code)
        if h_df is not None:
            fig = go.Figure(data=[go.Candlestick(x=h_df.index if '日期' not in h_df.columns else h_df['日期'],
                            open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=350)
            st.plotly_chart(fig, use_container_width=True)
            status.update(label="✅ 个股数据同步成功", state="complete")
        else:
            st.error("⚠️ 警告：当前所有行情源均繁忙，请稍后再试。")

# --- 底部：双窗并行扫描 ---
if btn_scan:
    col_left, col_right = st.columns(2)
    
    with st.spinner("正在并发穿透多个数据源..."):
        spot_df, active_source = get_market_snapshot()
        
    if spot_df is not None:
        st.caption(f"当前在线数据源：{active_source}")
        # 统一清洗数据列名（东财和新浪列名不同，需兼容）
        if '成交额' not in spot_df.columns and 'amount' in spot_df.columns:
            spot_df = spot_df.rename(columns={'amount': '成交额', 'code': '代码', 'name': '名称', 'open': '今开', 'trade': '最新价', 'high': '最高', 'low': '最低'})
        
        spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')
        pool = spot_df[spot_df['成交额'] >= vol_limit * 100000000].copy()
        
        # --- 左窗：阴线十字星 ---
        with col_left:
            st.subheader("🟢 阴线十字星监控")
            res_star = []
            for _, row in pool.iterrows():
                try:
                    o, c, h, l = float(row['今开']), float(row['最新价']), float(row['最高']), float(row['最低'])
                    if c < o and (h-l) > 0:
                        if (abs(o-c)/(h-l)) <= 0.12:
                            res_star.append({"代码":row['代码'], "名称":row['名称'], "涨跌":row.get('涨跌幅', 0)})
                except: continue
            st.dataframe(pd.DataFrame(res_star), use_container_width=True)
        
        # --- 右窗：金叉深度预警 ---
        with col_right:
            st.subheader("⚡ 金叉趋势扫描")
            res_gold = []
            top_pool = pool.sort_values('成交额', ascending=False).head(20)
            g_progress = st.progress(0)
            for i, (idx, row) in enumerate(top_pool.iterrows()):
                g_progress.progress((i+1)/len(top_pool))
                h_df_g = get_hist_with_retry(row['代码'])
                if h_df_g is not None and len(h_df_g) >= 15:
                    l9, h9 = h_df_g['最低'].rolling(9).min(), h_df_g['最高'].rolling(9).max()
                    rsv = (h_df_g['收盘'] - l9) / (h9 - l9) * 100
                    k = rsv.ewm(com=2).mean()
                    d = k.ewm(com=2).mean()
                    j = 3*k - 2*d
                    if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
                        res_gold.append({"代码":row['代码'], "名称":row['名称'], "J值":round(j.iloc[-1],2)})
            st.dataframe(pd.DataFrame(res_gold), use_container_width=True)
    else:
        st.error("❌ 无法连接到任何行情服务器，请检查网络或点击重置。")
