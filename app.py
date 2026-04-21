import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go

# --- 1. 界面与风格配置 ---
st.set_page_config(page_title="NIQING | 侧边栏终端", layout="wide")

# 自定义 CSS 强化侧边栏视觉
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .stButton>button { width: 100%; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 辅助计算函数 ---
def get_kdj_data(symbol):
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(30)
        low_9 = df['最低'].rolling(9).min()
        high_9 = df['最高'].rolling(9).max()
        rsv = (df['收盘'] - low_9) / (high_9 - low_9) * 100
        k = rsv.ewm(com=2).mean()
        d = k.ewm(com=2).mean()
        j = 3 * k - 2 * d
        # 金叉判定：今日J>D 且 昨日J<=D
        is_gold = j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]
        return True, is_gold, round(j.iloc[-1], 2)
    except:
        return False, False, 0

# --- 3. 左侧控制中心 (Sidebar) ---
with st.sidebar:
    st.title("妮情 · 策略控制")
    st.divider()
    
    # 窗口 1: 个股深度搜索控制
    st.subheader("🔍 个股搜索窗口")
    search_code = st.text_input("输入股票代码 (回车)", placeholder="例如: 600519", key="side_search")
    
    st.divider()
    
    # 窗口 2: 阴线十字星控制
    st.subheader("🟢 阴线十字星预警")
    vol_star = st.number_input("准入成交额 (亿)", value=5.0, step=1.0)
    strict_star = st.slider("十字星灵敏度", 0.05, 0.20, 0.12)
    btn_star = st.button("开始扫描阴线信号")
    
    st.divider()
    
    # 窗口 3: 金叉预警控制
    st.subheader("⚡ 金叉行情预警")
    vol_gold = st.number_input("活跃额门槛 (亿)", value=8.0, step=1.0)
    btn_gold = st.button("开始扫描金叉信号")
    
    st.divider()
    st.caption("NIQING STUDIO v2.0")

# --- 4. 右侧结果展示区 (Main Content) ---
st.header("NIQING STUDIO · 实时量能监测终端")

# A. 结果展示：个股深度透视
if search_code:
    st.subheader(f"📊 个股深度透视: {search_code}")
    try:
        h_df = ak.stock_zh_a_hist(symbol=search_code, period="daily", adjust="qfq").tail(45)
        fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                        high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
        fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=450, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        # 联动检测该股金叉状态
        succ, gold, j_val = get_kdj_status = get_kdj_data(search_code)
        if succ:
            status_txt = "🚀 已达成金叉" if gold else "⌛ 暂未金叉"
            st.metric(f"{search_code} 趋势雷达", status_txt, f"当前J值: {j_val}")
    except:
        st.error("无法调取该股票数据，请确认代码正确或接口通畅")

# B. 结果展示：阴线十字星
if btn_star:
    st.subheader("🟢 扫描结果：阴线十字星个股")
    with st.spinner("正在筛选缩量变盘信号..."):
        try:
            spot = ak.stock_zh_a_spot_em()
            spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
            # 过滤成交额 -> 过滤阴线(最新价<开盘) -> 过滤十字星形态
            pool = spot[spot['成交额'] >= vol_star * 100000000].copy()
            res_star = []
            for _, row in pool.iterrows():
                o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                if c < o and (h - l) > 0:
                    if (abs(o - c) / (h - l)) <= strict_star:
                        res_star.append({"代码": row['代码'], "名称": row['名称'], "价格": c, "跌幅%": row['涨跌幅'], "量额(亿)": round(row['成交额']/1e8, 2)})
            if res_star:
                st.dataframe(pd.DataFrame(res_star), use_container_width=True)
            else:
                st.warning("当前市场未发现符合条件的阴线十字星信号")
        except:
            st.error("数据源繁忙，请稍后再试")

# C. 结果展示：金叉预警
if btn_gold:
    st.subheader("⚡ 扫描结果：活跃股金叉预警")
    with st.spinner("正在计算大资金趋势..."):
        try:
            spot = ak.stock_zh_a_spot_em()
            spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
            # 取成交额前 50 的最活跃股进行深度金叉计算
            pool_gold = spot[spot['成交额'] >= vol_gold * 100000000].sort_values('成交额', ascending=False).head(50)
            res_gold = []
            for _, row in pool_gold.iterrows():
                succ, gold, j_val = get_kdj_data(row['代码'])
                if succ and gold:
                    res_gold.append({"代码": row['代码'], "名称": row['名称'], "最新价": row['最新价'], "J值": j_val, "状态": "⚡ 金叉达成"})
            if res_gold:
                st.dataframe(pd.DataFrame(res_gold), use_container_width=True)
            else:
                st.warning("高活跃资金池中暂无金叉信号")
        except:
            st.error("连接超时，请降低频率重试")

# 默认状态
if not search_code and not btn_star and not btn_gold:
    st.info("💡 终端就绪。请在左侧侧边栏执行搜索或扫描操作。")
