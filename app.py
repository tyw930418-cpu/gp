import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="NIQING | 侧边栏量能终端", layout="wide")

# --- 2. 核心计算函数 ---
def get_kdj_status(symbol):
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(30)
        low_9 = df['最低'].rolling(9).min()
        high_9 = df['最高'].rolling(9).max()
        rsv = (df['收盘'] - low_9) / (high_9 - low_9) * 100
        k = rsv.ewm(com=2).mean()
        d = k.ewm(com=2).mean()
        j = 3 * k - 2 * d
        # 金叉判定
        is_gold = j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]
        return True, is_gold, round(j.iloc[-1], 2)
    except:
        return False, False, 0

# --- 3. 左侧边栏 (控制中心) ---
with st.sidebar:
    st.title("妮情 · 策略控制")
    st.divider()
    
    # 模块一：个股深度搜索
    st.subheader("🔍 个股搜索窗口")
    search_code = st.text_input("输入代码 (如 600519)", placeholder="回车确认搜索")
    
    st.divider()
    
    # 模块二：阴线十字星设置
    st.subheader("🟢 阴线十字星预警")
    min_vol_star = st.number_input("十字星准入额 (亿)", value=5.0)
    star_strict = st.slider("十字星灵敏度", 0.05, 0.20, 0.12)
    btn_star = st.button("开始扫描阴线信号")
    
    st.divider()
    
    # 模块三：金叉预警设置
    st.subheader("⚡ 金叉行情预警")
    min_vol_gold = st.number_input("金叉准入额 (亿)", value=8.0)
    btn_gold = st.button("开始扫描金叉信号")

# --- 4. 右侧主屏幕 (结果展示区) ---
st.header("NIQING STUDIO · 实时量能监测终端")

# A. 展示搜索结果
if search_code:
    st.subheader(f"📊 个股分析: {search_code}")
    try:
        h_df = ak.stock_zh_a_hist(symbol=search_code, period="daily", adjust="qfq").tail(40)
        fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                        high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
        fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
        # 单独看该股金叉状态
        succ, gold, j_v = get_kdj_status(search_code)
        if succ:
            msg = "⚡ 已形成金叉" if gold else "⌛ 暂无金叉"
            st.metric("KDJ (J值)", j_v, msg)
    except:
        st.error("代码无效或数据请求失败")

# B. 展示阴线十字星结果
if btn_star:
    st.subheader("🟢 阴线十字星 - 扫描结果")
    with st.spinner("筛选中..."):
        try:
            data = ak.stock_zh_a_spot_em()
            data['成交额'] = pd.to_numeric(data['成交额'], errors='coerce')
            # 过滤：成交额 + 阴线(收盘<开盘) + 形态
            pool = data[data['成交额'] >= min_vol_star * 100000000].copy()
            res = []
            for _, row in pool.iterrows():
                o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                if c < o and (h - l) > 0:
                    if (abs(o - c) / (h - l)) <= star_strict:
                        res.append({"代码": row['代码'], "名称": row['名称'], "最新价": c, "涨跌%": row['涨跌幅'], "成交额(亿)": round(row['成交额']/1e8, 2)})
            if res:
                st.dataframe(pd.DataFrame(res), use_container_width=True)
            else:
                st.warning("未发现符合条件的阴线十字星")
        except:
            st.error("接口限流，请稍后再试")

# C. 展示金叉预警结果
if btn_gold:
    st.subheader("⚡ 活跃股金叉 - 扫描结果")
    with st.spinner("深度计算中..."):
        try:
            data = ak.stock_zh_a_spot_em()
            data['成交额'] = pd.to_numeric(data['成交额'], errors='coerce')
            pool = data[data['成交额'] >= min_vol_gold * 100000000].sort_values('成交额', ascending=False).head(40)
            gold_list = []
            for _, row in pool.iterrows():
                succ, gold, j_v = get_kdj_status(row['代码'])
                if succ and gold:
                    gold_list.append({"代码": row['代码'], "名称": row['名称'], "最新价": row['最新价'], "J值": j_v})
            if gold_list:
                st.dataframe(pd.DataFrame(gold_list), use_container_width=True)
            else:
                st.warning("当前活跃池内暂无金叉信号")
        except:
            st.error("连接超时，请降低频率")

# 如果什么都没点，显示初始引导
if not search_code and not btn_star and not btn_gold:
    st.info("👈 请在左侧控制台输入股票代码或点击扫描按钮。")
