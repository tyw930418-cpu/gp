import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="NIQING | 量能雷达", layout="wide")

# 初始化状态，防止页面刷新报错
if "c_list" not in st.session_state: 
    st.session_state.c_list = pd.DataFrame()

st.title("妮情 · 量能信号全自动实时雷达")

# --- 2. 侧边栏参数 ---
with st.sidebar:
    st.header("⚙️ 策略参数")
    scan_limit = st.slider("扫描深度", 50, 200, 100)
    min_vol_val = st.number_input("准入成交额(万)", value=5000)

# --- 3. 核心扫描逻辑 ---
if st.button("🚀 启动全市场深度量能扫描"):
    with st.spinner("同步数据中..."):
        try:
            # 抓取实时行情
            all_data = ak.stock_zh_a_spot_em()
            if not all_data.empty:
                # 转换数值类型并清洗
                cols = ['最新价', '涨跌幅', '成交量', '成交额', '最高', '最低', '今开']
                all_data[cols] = all_data[cols].apply(pd.to_numeric, errors='coerce')
                
                # 过滤高活跃池
                pool = all_data[all_data['成交额'] >= min_vol_val * 10000].sort_values('成交额', ascending=False).head(scan_limit)
                
                c_res = []
                for _, row in pool.iterrows():
                    # 绿色十字星简易监控逻辑
                    if row['今开'] > row['最新价'] and (row['最高'] - row['最低']) > 0:
                        diff = abs(row['今开'] - row['最新价']) / (row['最高'] - row['最低'])
                        if diff < 0.15:
                            c_res.append({
                                "代码": row['代码'], "名称": row['名称'], "涨跌幅%": row['涨跌幅'],
                                "最新价": row['最新价'], "成交量(手)": int(row['成交量']),
                                "成交额(亿)": round(row['成交额']/1e8, 2)
                            })
                st.session_state.c_list = pd.DataFrame(c_res)
                st.success(f"同步成功，捕捉到 {len(c_res)} 个量能信号")
        except Exception as e:
            st.error(f"连接失败或接口维护中: {e}")

# --- 4. 结果展示 ---
st.subheader("💹 监控台结果")
st.dataframe(st.session_state.c_list, use_container_width=True)

# --- 5. 深度量价透视 ---
if not st.session_state.c_list.empty:
    st.divider()
    selected = st.selectbox("🔍 选定个股深度量价透视", st.session_state.c_list['名称'].tolist())
    code = st.session_state.c_list[st.session_state.c_list['名称'] == selected]['代码'].values[0]
    
    try:
        h_df = ak.stock_zh_a_hist(symbol=code, adjust="qfq").tail(60)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        
        # K线图
        fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], 
                                     low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
        # 成交量
        fig.add_trace(go.Bar(x=h_df['日期'], y=h_df['成交量'], name="成交量", marker_color='gold'), row=2, col=1)
        
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.info("历史数据加载中...")
else:
    st.info("完成上方扫描后，此处将自动开启深度量价透视。")
