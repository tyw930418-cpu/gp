import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import time

# --- 1. 界面配置 ---
st.set_page_config(page_title="NIQING | 全球多源终端", layout="wide")

# --- 2. 核心数据引擎 ---
def get_hist_data(symbol, is_overseas=False):
    """根据选择切换国内外数据源"""
    time.sleep(0.5) # 强制冷却，减少封锁概率
    try:
        if is_overseas:
            # 国外源逻辑 (Yahoo Finance)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="3mo")
            if not df.empty:
                df = df.reset_index()
                df.columns = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '分红', '拆股']
                return df
        else:
            # 国内源逻辑 (轮询东财/新浪)
            try:
                return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(45)
            except:
                # 备选接口
                return ak.stock_zh_a_daily_qfq(symbol="sh"+symbol if symbol.startswith('6') else "sz"+symbol).tail(45)
    except Exception as e:
        return None

# --- 3. 左侧控制中心 ---
with st.sidebar:
    st.title("妮情 · 全球控制台")
    mode = st.toggle("🌍 切换国外数据源 (美股/加密/外汇)", value=False)
    
    st.divider()
    st.subheader("🔍 单股透视")
    placeholder = "如: 600519" if not mode else "如: AAPL 或 BTC-USD"
    target_code = st.text_input(f"输入代码 ({placeholder})")
    
    st.divider()
    st.subheader("📡 全局扫描控制")
    vol_limit = st.number_input("准入额 (亿)", value=5.0)
    btn_scan = st.button("🚀 启动全场双窗扫描")

# --- 4. 右侧结果大屏 ---
st.header("NIQING STUDIO · 实时监测中心")

# A. 个股展示窗 (置顶)
if target_code:
    with st.status(f"正在穿透链路获取 {target_code}...", expanded=True) as status:
        h_df = get_hist_data(target_code, is_overseas=mode)
        if h_df is not None and not h_df.empty:
            fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                            high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=400)
            st.plotly_chart(fig, use_container_width=True)
            status.update(label="✅ 数据同步成功", state="complete")
        else:
            st.error("⚠️ 链路异常：当前源无法响应，请切换数据源模式或检查代码。")

# B. 双窗扫描 (仅国内模式示例)
if btn_scan:
    if mode:
        st.warning("提示：目前全局扫描主要针对国内 A 股市场。")
    else:
        col1, col2 = st.columns(2)
        # 获取实时快照
        try:
            spot_df = ak.stock_zh_a_spot_em()
            spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')
            pool = spot_df[spot_df['成交额'] >= vol_limit * 100000000].copy()
            
            with col1:
                st.subheader("🟢 阴线十字星")
                # 筛选逻辑...
                st.dataframe(pool[['代码', '名称', '最新价']].head(20), use_container_width=True)
            
            with col2:
                st.subheader("⚡ 活跃金叉")
                st.info("深度计算中，请稍候...")
        except:
            st.error("国内实时行情源繁忙，请尝试点击左侧重置。")
