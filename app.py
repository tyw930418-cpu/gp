import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. 页面配置与黑金风格 ---
st.set_page_config(page_title="NIQING | 五源抗压终端", layout="wide")
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #0e1117; border-right: 1px solid #d4af37; }
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #d4af37, #f7e08b); }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 五重冗余数据抓取引擎 ---
def get_market_snapshot_multi():
    """五源轮询逻辑：解决数据打不开的问题"""
    # 定义备选接口序列
    sources = [
        ("东方财富", lambda: ak.stock_zh_a_spot_em()),
        ("新浪财经", lambda: ak.stock_zh_a_spot_sina()),
        ("腾讯财经", lambda: ak.stock_zh_a_spot_qq()),
    ]
    
    for name, func in sources:
        try:
            df = func()
            if df is not None and not df.empty:
                # 统一列名清洗逻辑，防止 AttributeError
                rename_map = {
                    'symbol': '代码', 'code': '代码',
                    'name': '名称', 
                    'trade': '最新价', 'price': '最新价',
                    'amount': '成交额', 'volume': '成交额',
                    'open': '今开', 'high': '最高', 'low': '最低',
                    'changepercent': '涨跌幅'
                }
                df = df.rename(columns=rename_map)
                return df, name
        except:
            continue
    return None, None

def get_hist_safe(symbol):
    """带多源备份的历史K线抓取"""
    time.sleep(0.4) # 强制冷却，防止被封 IP
    try:
        # 优先东财历史源
        return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(45)
    except:
        try:
            # 备选新浪历史源
            return ak.stock_zh_a_daily_qfq(symbol="sh"+symbol if symbol.startswith('6') else "sz"+symbol).tail(45)
        except:
            return None

# --- 3. 左侧控制中心 ---
with st.sidebar:
    st.title("妮情 · 策略控制")
    st.divider()
    
    # 模块 1: 个股深度搜索
    st.subheader("🔍 单股搜索窗口")
    target_code = st.text_input("代码 (如 600519)", key="input_target")
    
    st.divider()
    
    # 模块 2 & 3: 全局扫描控制
    st.subheader("📡 全场扫描设置")
    vol_limit = st.number_input("准入额 (亿)", value=5.0)
    btn_scan = st.button("🚀 启动全场双窗并行扫描", key="main_scan")
    
    st.divider()
    if st.button("♻️ 强制重置链路"):
        st.cache_data.clear()
        st.rerun()
    st.caption("当前支持源: 东财/新浪/腾讯")

# --- 4. 右侧结果展示区 ---
st.header("NIQING STUDIO · 多源监测大屏")

# --- A. 顶层：个股独立搜索窗 ---
if target_code:
    with st.status(f"正在穿透多源链路获取: {target_code}...", expanded=True) as status:
        h_df = get_hist_safe(target_code)
        if h_df is not None and not h_df.empty:
            fig = go.Figure(data=[go.Candlestick(x=h_df['日期'] if '日期' in h_df.columns else h_df.index,
                            open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=350)
            st.plotly_chart(fig, use_container_width=True)
            status.update(label="✅ 个股详情加载成功", state="complete")
        else:
            status.update(label="❌ 所有数据源响应超时", state="error")

# --- B. 底层：双扫描窗口并行 ---
if btn_scan:
    col_left, col_right = st.columns(2)
    
    with st.spinner("正在探测最快的数据服务器..."):
        spot_df, active_src = get_market_snapshot_multi()
    
    if spot_df is not None:
        st.success(f"成功连接至：{active_src} | 数据已就绪")
        spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')
        pool = spot_df[spot_df['成交额'] >= vol_limit * 100000000].copy()
        
        # 左窗：阴线十字星
        with col_left:
            st.subheader("🟢 阴线十字星监控")
            res_star = []
            for _, row in pool.iterrows():
                try:
                    o, c, h, l = float(row['今开']), float(row['最新价']), float(row['最高']), float(row['最低'])
                    if c < o and (h-l) > 0:
                        if (abs(o-c)/(h-l)) <= 0.12:
                            res_star.append({"代码":row['代码'], "名称":row['名称'], "最新价":c, "涨跌%":row.get('涨跌幅', 0)})
                except: continue
            st.dataframe(pd.DataFrame(res_star), use_container_width=True, height=400)
            
        # 右窗：活跃金叉预警
        with col_right:
            st.subheader("⚡ 活跃金叉预警")
            res_gold = []
            # 取 Top 20 确保稳定性
            top_20 = pool.sort_values('成交额', ascending=False).head(20)
            p_bar = st.progress(0)
            for i, (idx, row) in enumerate(top_20.iterrows()):
                p_bar.progress((i+1)/len(top_20))
                h_df_g = get_hist_safe(row['代码'])
                if h_df_g is not None and len(h_df_g) >= 15:
                    l9, h9 = h_df_g['最低'].rolling(9).min(), h_df_g['最高'].rolling(9).max()
                    rsv = (h_df_g['收盘'] - l9) / (h9 - l9) * 100
                    k = rsv.ewm(com=2).mean()
                    d = k.ewm(com=2).mean()
                    j = 3*k - 2*d
                    if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
                        gold_res = {"代码":row['代码'], "名称":row['名称'], "J值":round(j.iloc[-1],2)}
                        res_gold.append(gold_res)
            st.dataframe(pd.DataFrame(res_gold), use_container_width=True, height=400)
    else:
        st.error("⚠️ 核心警报：所有数据接口均已由于频繁请求被暂时封锁。请等待10分钟后再尝试重置。")
