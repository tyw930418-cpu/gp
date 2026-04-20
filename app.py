import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 配置与授权 ---
st.set_page_config(page_title="NIQING | 行业金叉监控", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 2. 核心引擎 ---
class ProEngine:
    @staticmethod
    def safe_fetch(func, **kwargs):
        for _ in range(3):
            try:
                time.sleep(random.uniform(0.2, 0.5))
                return func(**kwargs)
            except: time.sleep(1)
        return pd.DataFrame()

    @staticmethod
    def calc_kdj(df):
        low_9 = df['最低'].rolling(9).min()
        high_9 = df['最高'].rolling(9).max()
        rsv = (df['收盘'] - low_9) / (high_9 - low_9) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df

# --- 3. UI 界面布局 ---
st.title("妮情 · 行业分类与金叉预警")

# 侧边栏：行业选择
st.sidebar.header("📂 市场筛选")
# 预设一些热门行业，或者你可以留空让它自动获取
industry_list = ["半导体", "电力行业", "通信设备", "汽车整车", "酿酒行业", "生物制品", "互联网服务"]
selected_industry = st.sidebar.selectbox("选择目标行业", industry_list)

# 核心容器
col_list, col_chart = st.columns([1, 2])

with col_list:
    st.subheader(f"📍 {selected_industry} 成员")
    if st.button("同步行业数据"):
        # 获取行业板块成员
        df_ind = ProEngine.safe_fetch(ak.stock_board_industry_cons_em, symbol=selected_industry)
        if not df_ind.empty:
            st.session_state.ind_data = df_ind[['代码', '名称', '最新价', '涨跌幅']]
        else:
            st.error("行业数据同步失败")
    
    if "ind_data" in st.session_state:
        # 在界面上让用户选择具体股票
        selected_stock_name = st.selectbox("选择个股进行金叉检测", st.session_state.ind_data['名称'].tolist())
        target_code = st.session_state.ind_data[st.session_state.ind_data['名称'] == selected_stock_name]['代码'].values[0]
        st.write(f"已选中：{selected_stock_name} ({target_code})")
    else:
        st.info("请先同步行业数据")
        target_code = None

with col_chart:
    if target_code:
        with st.spinner("正在扫描金叉信号..."):
            h_df = ProEngine.safe_fetch(ak.stock_zh_a_hist, symbol=target_code, adjust="qfq")
            if not h_df.empty:
                h_df = ProEngine.calc_kdj(h_df)
                
                # --- 金叉检测提示逻辑 ---
                last = h_df.iloc[-1]
                prev = h_df.iloc[-2]
                is_golden = (prev['K'] < prev['D']) and (last['K'] > last['D'])
                
                if is_golden:
                    # 1. 顶部大横幅提示
                    st.success(f"🔥 金叉预警：{selected_stock_name} 今日触发 KDJ 金叉！")
                    # 2. 右下角气泡
                    st.toast(f"{selected_stock_name} 出现金叉信号！", icon="⭐")
                else:
                    st.info("当前指标平稳，暂无金叉信号")

                # 绘图显示
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
                fig.add_trace(go.Scatter(x=h_df['日期'], y=h_df['J'], line=dict(color='purple', width=2), name="KDJ-J"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

# --- 4. 实时监控大厅 ---
st.title("妮情 · A股抗干扰实时雷达")

tab1, tab2 = st.tabs(["📡 实时监控大厅", "📈 深度指标回测"])

with tab1:
    c1, c2 = st.columns([1, 4])
    with c1:
        is_live = st.toggle("开启实时雷达", value=False)
        rate = st.select_slider("刷新频率 (秒)", options=[30, 60, 120, 300], value=60)
    
    status_bar = st.empty()
    data_display = st.empty()

    while is_live:
        now = datetime.now().strftime("%H:%M:%S")
        status_bar.info(f"正在同步数据... (最后尝试: {now})")
        
        # 使用安全抓取
        raw_df = RobustEngine.safe_fetch(ak.stock_zh_a_spot_em)
        
        if not raw_df.empty:
            raw_df[['最新价', '今开', '最高', '最低', '成交额']] = raw_df[['最新价', '今开', '最高', '最低', '成交额']].apply(pd.to_numeric, errors='coerce')
            # 这里的过滤逻辑保持你之前的阴线十字星
            raw_df['entity_pct'] = (raw_df['今开'] - raw_df['最新价']).abs() / (raw_df['最高'] - raw_df['最低'] + 0.001)
            mask = (raw_df['最新价'] < raw_df['今开']) & (raw_df['entity_pct'] < 0.2) & (raw_df['成交额'] > 50000000)
            
            res = raw_df[mask].copy()
            status_bar.success(f"🟢 监控中 | 更新时间: {now} | 捕获信号: {len(res)}")
            data_display.dataframe(res.sort_values('成交额', ascending=False), use_container_width=True, height=500)
            if not res.empty: st.toast("捕获新信号！")
        else:
            status_bar.warning(f"🟡 网络波动中，正在等待下一轮重连... (最后尝试: {now})")
            
        time.sleep(rate)
        if not is_live: break

with tab2:
    code = st.text_input("输入代码深度分析", "600519")
    if code:
        # 同样使用安全抓取获取历史数据
        h_df = RobustEngine.safe_fetch(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq")
        if not h_df.empty:
            h_df = RobustEngine.calc_kdj(h_df)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4])
            fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
            fig.add_trace(go.Scatter(x=h_df['日期'], y=h_df['J'], line=dict(color='purple'), name="KDJ-J"), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("无法连接到数据源，请检查代码或稍后再试。")
