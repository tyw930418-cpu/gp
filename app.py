import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="NIQING | 三位一体雷达", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    stDataFrame { border: 1px solid #d4af37; }
    </style>
    """, unsafe_allow_html=True)

st.title("妮情 · 全自动量能雷达终端 (三窗口版)")

# --- 2. 核心计算函数 ---
def get_kdj_data(symbol):
    """获取数据并计算KDJ"""
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(30)
        low_9 = df['最低'].rolling(9).min()
        high_9 = df['最高'].rolling(9).max()
        rsv = (df['收盘'] - low_9) / (high_9 - low_9) * 100
        k = rsv.ewm(com=2).mean()
        d = k.ewm(com=2).mean()
        j = 3 * k - 2 * d
        return True, j.iloc[-1], d.iloc[-1], j.iloc[-2], d.iloc[-2]
    except:
        return False, 0, 0, 0, 0

# --- 3. 布局：三个独立的窗口 ---
tab1, tab2, tab3 = st.tabs(["🔍 个股深度搜索", "🟢 阴线十字星监控", "⚡ 金叉预警监控"])

# --- 窗口 1: 个股深度搜索 ---
with tab1:
    st.subheader("个股全维度透视")
    search_code = st.text_input("输入股票代码 (如 600519)", key="search_1")
    if search_code:
        try:
            h_df = ak.stock_zh_a_hist(symbol=search_code, period="daily", adjust="qfq").tail(60)
            fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                            high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(title=f"{search_code} 走势透视", template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            st.table(h_df.tail(5))
        except:
            st.error("代码输入有误或数据源连接中断")

# --- 窗口 2: 阴线十字星监控 ---
with tab2:
    st.subheader("全市场阴线十字星扫描")
    col_a, col_b = st.columns(2)
    min_v = col_a.number_input("准入成交额(亿)", value=5.0, key="v2")
    star_r = col_b.slider("十字星灵敏度", 0.05, 0.20, 0.12, key="s2")
    
    if st.button("开始扫描阴线信号"):
        with st.spinner("信号捕捉中..."):
            try:
                data = ak.stock_zh_a_spot_em()
                data['成交额'] = pd.to_numeric(data['成交额'], errors='coerce')
                # 过滤条件：成交额 + 阴线(收盘<开盘) + 十字星(实体占比)
                pool = data[data['成交额'] >= min_v * 100000000].copy()
                res = []
                for _, row in pool.iterrows():
                    o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                    if c < o and (h - l) > 0: # 必须是阴线且有振幅
                        if (abs(o - c) / (h - l)) <= star_r:
                            res.append({"代码": row['代码'], "名称": row['名称'], "价格": c, "涨跌%": row['涨跌幅'], "量能(亿)": round(row['成交额']/1e8, 2)})
                st.dataframe(pd.DataFrame(res), use_container_width=True)
            except:
                st.error("接口限流，请稍后再试")

# --- 窗口 3: 金叉预警监控 ---
with tab3:
    st.subheader("量能活跃金叉预警")
    col_c, col_d = st.columns(2)
    v_limit = col_c.number_input("成交额门槛(亿)", value=8.0, key="v3")
    search_kdj = col_d.text_input("查询特定个股金叉", key="search_3")
    
    if st.button("扫描全场金叉"):
        with st.spinner("计算趋势中..."):
            try:
                data = ak.stock_zh_a_spot_em()
                data['成交额'] = pd.to_numeric(data['成交额'], errors='coerce')
                pool = data[data['成交额'] >= v_limit * 100000000].head(50).copy() # 仅限前50活跃
                gold_res = []
                for _, row in pool.iterrows():
                    success, j, d, pj, pd_ = get_kdj_data(row['代码'])
                    if success and j > d and pj <= pd_:
                        gold_res.append({"代码": row['代码'], "名称": row['名称'], "J值": round(j, 2), "状态": "🚀 已金叉"})
                st.dataframe(pd.DataFrame(gold_res), use_container_width=True)
            except:
                st.error("数据连接超时")
                
    if search_kdj:
        success, j, d, pj, pd_ = get_kdj_data(search_kdj)
        if success:
            state = "⚡ 正在金叉" if j > d and pj <= pd_ else "⌛ 暂未金叉"
            st.metric(f"{search_kdj} 状态", state, f"J值: {round(j,2)}")
