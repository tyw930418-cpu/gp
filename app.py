import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="NIQING | 多源并行雷达", layout="wide")
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #0e1117; border-right: 1px solid #d4af37; }
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #d4af37, #f7e08b); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 增强版数据抓取逻辑 ---
def get_market_snapshot():
    """修复 AttributeError，兼容多源列名"""
    try:
        # 一号源：东财 (实时快照)
        df = ak.stock_zh_a_spot_em()
        if df is not None: return df, "东方财富"
    except:
        try:
            # 二号源：新浪 (备用)
            df = ak.stock_zh_a_spot_sina()
            if df is not None:
                # 统一新浪和东财的列名映射
                mapping = {'symbol': '代码', 'name': '名称', 'trade': '最新价', 'amount': '成交额', 'open': '今开', 'high': '最高', 'low': '最低', 'changepercent': '涨跌幅'}
                return df.rename(columns=mapping), "新浪财经"
        except:
            return None, None

def get_hist_safe(symbol):
    """带延迟的个股数据获取"""
    time.sleep(0.3)
    try:
        # 优先使用东财日线接口
        return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(40)
    except:
        return None

# --- 3. 左侧控制中心 ---
with st.sidebar:
    st.title("妮情 · 策略控制")
    
    # 模块 1: 个股搜索
    st.subheader("🔍 单股搜索窗口")
    target_code = st.text_input("代码 (如 600519)", key="input_target")
    
    st.divider()
    
    # 模块 2 & 3: 全局扫描
    st.subheader("📡 全场扫描设置")
    vol_limit = st.number_input("准入额 (亿)", value=5.0)
    btn_scan = st.button("🚀 启动全场双窗并行扫描", key="main_scan")
    
    st.divider()
    if st.button("♻️ 强制重置链路"):
        st.cache_data.clear()
        st.rerun()

# --- 4. 右侧结果展示区 ---
st.header("NIQING STUDIO · 多源监测大屏")

# A. 顶层：个股详情窗口 (始终独立)
if target_code:
    with st.status(f"🔍 正在穿透个股数据: {target_code}...", expanded=True) as status:
        h_df = get_hist_safe(target_code)
        if h_df is not None and not h_df.empty:
            fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                            high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=350)
            st.plotly_chart(fig, use_container_width=True)
            status.update(label="✅ 个股详情已同步", state="complete")
        else:
            status.update(label="❌ 该代码数据抓取失败", state="error")

# B. 底层：双扫描窗口并行
if btn_scan:
    col_left, col_right = st.columns(2)
    
    with st.spinner("正在并发请求多个数据中心..."):
        spot_df, active_src = get_market_snapshot()
    
    if spot_df is not None:
        st.caption(f"当前链路：{active_src} | 实时同步中")
        spot_df['成交额'] = pd.to_numeric(spot_df['成交额'], errors='coerce')
        # 过滤准入池
        active_pool = spot_df[spot_df['成交额'] >= vol_limit * 100000000].copy()
        
        # 左窗：阴线十字星
        with col_left:
            st.subheader("🟢 阴线十字星监控")
            res_star = []
            for _, row in active_pool.iterrows():
                try:
                    o, c, h, l = float(row['今开']), float(row['最新价']), float(row['最高']), float(row['最低'])
                    if c < o and (h-l) > 0: # 阴线
                        if (abs(o-c)/(h-l)) <= 0.12: # 十字星
                            res_star.append({"代码":row['代码'], "名称":row['名称'], "价格":c, "涨跌%":row.get('涨跌幅', 0)})
                except: continue
            st.dataframe(pd.DataFrame(res_star), use_container_width=True, height=400)
            
        # 右窗：活跃金叉扫描
        with col_right:
            st.subheader("⚡ 活跃金叉预警")
            res_gold = []
            # 限制 Top 25 避免被封
            top_25 = active_pool.sort_values('成交额', ascending=False).head(25)
            p_bar = st.progress(0)
            for i, (idx, row) in enumerate(top_25.iterrows()):
                p_bar.progress((i+1)/len(top_25))
                h_df_g = get_hist_safe(row['代码'])
                if h_df_g is not None and len(h_df_g) >= 15:
                    l9, h9 = h_df_g['最低'].rolling(9).min(), h_df_g['最高'].rolling(9).max()
                    rsv = (h_df_g['收盘'] - l9) / (h9 - l9) * 100
                    k = rsv.ewm(com=2).mean()
                    d = k.ewm(com=2).mean()
                    j = 3*k - 2*d
                    if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
                        res_gold.append({"代码":row['代码'], "名称":row['名称'], "J值":round(j.iloc[-1],2)})
            st.dataframe(pd.DataFrame(res_gold), use_container_width=True, height=400)
    else:
        st.error("⚠️ 警告：当前所有行情接口（东财/新浪）均无法响应，请等待 5 分钟后再试。")
