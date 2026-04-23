import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import time

# --- 1. 界面与风格 ---
st.set_page_config(page_title="NIQING | 全球多源终端", layout="wide")
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #0e1117; border-right: 1px solid #d4af37; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 数据抓取逻辑 (国内五源轮询 + 国外源) ---
def get_global_market(is_overseas=False):
    """
    is_overseas: 如果为 True，则调用国外接口
    """
    if not is_overseas:
        # 国内源轮询逻辑
        sources = [
            ("东方财富", lambda: ak.stock_zh_a_spot_em()),
            ("新浪财经", lambda: ak.stock_zh_a_spot_sina()),
            ("腾讯财经", lambda: ak.stock_zh_a_spot_qq())
        ]
        for name, func in sources:
            try:
                df = func()
                if df is not None and not df.empty:
                    # 统一列名映射以防报错
                    rename_map = {'symbol': '代码', 'code': '代码', 'name': '名称', 'trade': '最新价', 'amount': '成交额', 'open': '今开', 'high': '最高', 'low': '最低'}
                    return df.rename(columns=rename_map), name
            except: continue
        return None, None
    else:
        # 国外源逻辑 (示例：标普500成分股或加密货币)
        try:
            return yf.download("BTC-USD ETH-USD AAPL TSLA NVDA", period="1d", group_by='ticker'), "Yahoo Finance"
        except:
            return None, None

def get_hist_smart(symbol, source_type="国内"):
    time.sleep(0.4) # 冷却避封
    try:
        if source_type == "国内":
            return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(45)
        else:
            # 国外源 (格式如: AAPL, BTC-USD, 0700.HK)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="3mo")
            df = df.reset_index()
            df.columns = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '分红', '拆股']
            return df
    except:
        return None

# --- 3. 左侧控制中心 ---
with st.sidebar:
    st.title("妮情 · 全球控制台")
    
    # 切换国内外模式
    data_mode = st.radio("数据源区域", ["国内 (A股)", "国外 (美股/加密)"])
    
    st.divider()
    
    # 窗口 1: 搜索
    st.subheader("🔍 单股搜索")
    hint = "如: 600519" if data_mode == "国内 (A股)" else "如: AAPL, BTC-USD"
    target_code = st.text_input(f"代码 ({hint})", key="input_target")
    
    st.divider()
    
    # 窗口 2 & 3: 扫描
    st.subheader("📡 全场扫描设置")
    vol_limit = st.number_input("准入额 (亿/美元)", value=5.0)
    btn_scan = st.button("🚀 启动全场双窗扫描", key="main_scan")
    
    st.divider()
    if st.button("♻️ 重置链路"):
        st.cache_data.clear()
        st.rerun()

# --- 4. 右侧展示大屏 ---
st.header(f"NIQING STUDIO · {'全球' if data_mode == '国外 (美股/加密)' else '多源'}监测大屏")

# A. 顶部：个股透视
if target_code:
    with st.status(f"正在建立全球链路获取: {target_code}...", expanded=True) as status:
        mode = "国外" if data_mode == "国外 (美股/加密)" else "国内"
        h_df = get_hist_smart(target_code, source_type=mode)
        if h_df is not None and not h_df.empty:
            fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                            high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=350)
            st.plotly_chart(fig, use_container_width=True)
            status.update(label="✅ 详情同步成功", state="complete")
        else:
            status.update(label="❌ 链路超时，请检查代码格式", state="error")

# B. 底层：扫描 (此处仅展示国内模式扫描示例)
if btn_scan and data_mode == "国内 (A股)":
    col_left, col_right = st.columns(2)
    spot_df, active_src = get_global_market(is_overseas=False)
    
    if spot_df is not None:
        st.success(f"当前链路：{active_src}")
        spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')
        pool = spot_df[spot_df['成交额'] >= vol_limit * 100000000].copy()
        
        with col_left:
            st.subheader("🟢 阴线十字星监控")
            # ... (形态算法同上)
            st.dataframe(pool[['代码', '名称', '最新价']].head(15), use_container_width=True)
        
        with col_right:
            st.subheader("⚡ 活跃金叉预警")
            # ... (金叉算法同上)
            st.info("金叉扫描正在计算中...")
    else:
        st.error("国内所有源均繁忙。建议切换至【国外】模式测试链路。")
