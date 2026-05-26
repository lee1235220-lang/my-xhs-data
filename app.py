"""
小红书矩阵内容赛马与数据洞察大屏 — Streamlit 前端（Supabase 版）
"""

import streamlit as st
import pandas as pd
import time

from supabase import create_client

# ============================================================
#   Supabase 云端初始化（通过 Streamlit Secrets 注入凭证）
# ============================================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

TABLE_NOTES    = "matrix_notes"
TABLE_ACCOUNTS = "accounts"

# ============================================================
#   主题打标规则（与上游爬虫保持一致）
# ============================================================
THEME_RULES = [
    ("美食探店", ["探店", "美食", "吃", "餐厅", "打卡"]),
    ("租房避坑", ["租房", "公寓", "避雷", "私房"]),
    ("行前干货", ["行李", "干货", "清单", "准备", "好物"]),
]


def tag_theme(title: str) -> str:
    """根据标题关键词返回主题标签"""
    if not title:
        return "日常通用"
    for theme, keywords in THEME_RULES:
        for kw in keywords:
            if kw in title:
                return theme
    return "日常通用"


# ============================================================
#   数据读取层（Supabase + Streamlit 缓存）
# ============================================================

@st.cache_data(ttl=600)
def load_notes() -> pd.DataFrame:
    """从 Supabase matrix_notes 表读取全量笔记"""
    resp = supabase.table(TABLE_NOTES).select("*").execute()
    if resp.data:
        return pd.DataFrame(resp.data)
    return pd.DataFrame()


@st.cache_data(ttl=600)
def load_accounts() -> pd.DataFrame:
    """从 Supabase accounts 表读取全量账号"""
    resp = supabase.table(TABLE_ACCOUNTS).select("*").order("id").execute()
    if resp.data:
        return pd.DataFrame(resp.data)
    return pd.DataFrame()


# ============================================================
#   账号 CRUD（写操作，需要刷新缓存）
# ============================================================

def add_account(name: str, url: str):
    """新增监控账号"""
    supabase.table(TABLE_ACCOUNTS).insert({"name": name, "url": url}).execute()
    st.cache_data.clear()


def delete_account(account_id: int):
    """删除账号及其关联笔记"""
    # 1. 查账号名
    resp = supabase.table(TABLE_ACCOUNTS).select("name").eq("id", account_id).execute()
    if resp.data:
        name = resp.data[0]["name"]
        # 2. 删笔记
        supabase.table(TABLE_NOTES).delete().eq("account_name", name).execute()
        # 3. 删账号
        supabase.table(TABLE_ACCOUNTS).delete().eq("id", account_id).execute()
    st.cache_data.clear()


# ============================================================
#   基于 DataFrame 的聚合查询（替代原 SQLite 查询）
# ============================================================

def get_stats(df_notes: pd.DataFrame, df_accounts: pd.DataFrame) -> dict:
    """核心统计指标"""
    return {
        "account_count":     len(df_accounts),
        "note_count":        len(df_notes),
        "max_likes":         int(df_notes["likes"].max()) if not df_notes.empty else 0,
        "total_comments":    int(df_notes["comments"].sum()) if not df_notes.empty else 0,
        "total_collections": int(df_notes["collections"].sum()) if not df_notes.empty else 0,
    }


def get_all_themes(df_notes: pd.DataFrame) -> list:
    """所有主题（去重排序）"""
    if df_notes.empty:
        return []
    return sorted(df_notes["theme"].dropna().unique().tolist())


def get_theme_data(df_notes: pd.DataFrame, theme: str, metric: str = "likes") -> list:
    """按主题、账号聚合指定度量"""
    valid = {"likes", "comments", "collections"}
    if metric not in valid:
        metric = "likes"
    filtered = df_notes[df_notes["theme"] == theme]
    if filtered.empty:
        return []
    grouped = (
        filtered.groupby("account_name")[metric]
        .sum()
        .reset_index()
        .sort_values(metric, ascending=False)
    )
    grouped.columns = ["account_name", f"total_{metric}"]
    return grouped.to_dict("records")


def get_notes_by_theme(df_notes: pd.DataFrame, theme: str) -> list:
    """按主题返回笔记详情，按点赞降序"""
    filtered = df_notes[df_notes["theme"] == theme]
    if filtered.empty:
        return []
    filtered = filtered.sort_values("likes", ascending=False)
    cols = ["account_name", "title", "theme", "likes", "comments",
            "collections", "publish_date", "link"]
    available = [c for c in cols if c in filtered.columns]
    return filtered[available].to_dict("records")


# ============================================================
#   Streamlit 页面配置
# ============================================================

st.set_page_config(
    page_title="小红书矩阵赛马大屏",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
<style>
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stMetricValue"] {font-size: 1.6rem !important;}
    .main-title {
        font-size: 1.8rem; font-weight: 700;
        background: linear-gradient(135deg, #FF5A5F, #E94057);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .cookie-hint {font-size: 0.8rem; color: #999; margin-top: -8px;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- 侧边栏导航 ----------
st.sidebar.markdown("## 📊 小红书矩阵赛马")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "导航",
    ["📈 数据赛马大屏", "🔄 启动数据同步", "👥 账号矩阵管理"],
    label_visibility="collapsed",
)

# ============================
#   📈 数据赛马大屏
# ============================
if page == "📈 数据赛马大屏":
    st.markdown(
        '<p class="main-title">🏇 小红书矩阵内容赛马大屏</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    col_refresh, *_ = st.columns([1, 6])
    if col_refresh.button("🔄 刷新数据"):
        st.cache_data.clear()
        st.rerun()

    # ── 加载云端数据 ──
    df_notes    = load_notes()
    df_accounts = load_accounts()
    stats       = get_stats(df_notes, df_accounts)

    # ── 五大核心指标卡片 ──
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("📋 监控账号数", stats["account_count"])
    with c2:
        st.metric("📝 已收录笔记数", stats["note_count"])
    with c3:
        st.metric("🔥 全盘最高点赞", stats["max_likes"])
    with c4:
        st.metric("💬 全盘总评论数", stats["total_comments"])
    with c5:
        st.metric("⭐ 全盘总收藏数", stats["total_collections"])

    st.markdown("---")

    themes = get_all_themes(df_notes)
    if not themes:
        st.info("暂无笔记数据，请先在「启动数据同步」页面同步数据。")
    else:
        # ── 跨号主题赛马图 ──
        st.subheader("🎯 跨号主题赛马图")

        col_theme, col_metric = st.columns([1, 1])
        with col_theme:
            selected_theme = st.selectbox("选择主题类型", themes, key="theme_select")
        with col_metric:
            metric_label_map = {
                "likes":       "👍 点赞数",
                "comments":    "💬 评论数",
                "collections": "⭐ 收藏数",
            }
            selected_metric_key = st.selectbox(
                "选择度量指标",
                list(metric_label_map.keys()),
                format_func=lambda k: metric_label_map[k],
                key="metric_select",
            )

        theme_stats = get_theme_data(df_notes, selected_theme, metric=selected_metric_key)
        metric_col = f"total_{selected_metric_key}"
        metric_label = metric_label_map[selected_metric_key]

        if theme_stats:
            df_bar = pd.DataFrame(theme_stats)
            df_bar = df_bar.rename(
                columns={"account_name": "账号名称", metric_col: metric_label}
            )
            df_bar = df_bar.set_index("账号名称")
            st.bar_chart(df_bar, use_container_width=True)
        else:
            st.warning(f"主题「{selected_theme}」暂无数据。")

        st.markdown("---")

        # ── 笔记透视表 ──
        st.subheader("📋 笔记透视表")
        notes = get_notes_by_theme(df_notes, selected_theme)
        if notes:
            df_notes_view = pd.DataFrame(notes)
            df_notes_view = df_notes_view.rename(
                columns={
                    "account_name": "账号",
                    "title":        "标题",
                    "theme":        "主题",
                    "likes":        "点赞数",
                    "comments":     "评论数",
                    "collections":  "收藏数",
                    "publish_date": "发布日期",
                    "link":         "链接",
                }
            )
            column_order = [
                "账号", "标题", "主题", "发布日期",
                "点赞数", "评论数", "收藏数", "链接",
            ]
            df_notes_view = df_notes_view[[c for c in column_order if c in df_notes_view.columns]]

            st.dataframe(
                df_notes_view,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "点赞数":  st.column_config.NumberColumn("点赞数", format="%d"),
                    "评论数":  st.column_config.NumberColumn("评论数", format="%d"),
                    "收藏数":  st.column_config.NumberColumn("收藏数", format="%d"),
                    "链接":    st.column_config.LinkColumn("链接"),
                },
            )
        else:
            st.info("暂无数据，等待同步。")

# ============================
#   🔄 启动数据同步
# ============================
elif page == "🔄 启动数据同步":
    st.markdown(
        '<p class="main-title">🔄 启动数据同步</p>', unsafe_allow_html=True
    )
    st.markdown("---")

    df_accounts = load_accounts()
    if df_accounts.empty:
        st.warning("⚠️ 尚未添加任何监控账号，请先去「账号矩阵管理」页面添加。")
    else:
        st.markdown(f"当前监控账号：**{len(df_accounts)}** 个")

        # ─── Cookie 输入区 ───
        st.markdown("### 🍪 小红书全局 Cookie")
        cookie_str = st.text_area(
            "请输入小红书全局 Cookie（必填，用于绕过登录墙）",
            placeholder=(
                "a1=18xxxxxxx; web_session=0300xxxxxx; "
                "webId=xxxxxx; gid=yjWxxxxx; "
                "acw_tc=xxxxx; ..."
            ),
            height=120,
            key="cookie_input",
        )
        st.caption(
            "📌 获取方式：浏览器登录小红书后，F12 → Application → Cookies → "
            "复制 xiaohongshu.com 下所有 Cookie，格式为 `key=value; key=value`"
        )

        st.markdown("---")

        if st.button("🚀 开始数据同步", type="primary", use_container_width=True):
            if not cookie_str or not cookie_str.strip():
                st.error("❌ 请先粘贴 Cookie 字符串，否则无法绕过登录弹窗。")
            else:
                log_placeholder = st.empty()

                def log_callback(msg: str):
                    now = time.strftime("%H:%M:%S")
                    if not hasattr(log_callback, "history"):
                        log_callback.history = []
                    log_callback.history.append(f"`[{now}]` {msg}")
                    log_placeholder.markdown(
                        "\n  \n".join(log_callback.history)
                    )

                with st.spinner("正在启动浏览器抓取数据，请稍候..."):
                    from spider import scrape_all_accounts

                    result = scrape_all_accounts(
                        cookie_str=cookie_str.strip(),
                        progress_callback=log_callback,
                    )

                # 同步完成后刷新云端缓存
                st.cache_data.clear()
                st.success(
                    f"✅ 同步完成！共处理 {result['total']} 个账号，"
                    f"收录 {result['new']} 篇新笔记。"
                )
                st.balloons()

# ============================
#   👥 账号矩阵管理
# ============================
elif page == "👥 账号矩阵管理":
    st.markdown(
        '<p class="main-title">👥 账号矩阵管理</p>', unsafe_allow_html=True
    )
    st.markdown("---")

    with st.expander("➕ 添加新账号", expanded=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            new_name = st.text_input("账号名称 *", placeholder="如：探店达人小王")
        with col2:
            new_url = st.text_input(
                "小红书主页链接 *",
                placeholder="https://www.xiaohongshu.com/user/profile/xxxxx",
            )
        if st.button("💾 保存账号", type="primary"):
            if not new_name.strip():
                st.error("请输入账号名称")
            elif not new_url.strip():
                st.error("请输入主页链接")
            elif not new_url.strip().startswith("http"):
                st.error("请输入有效的 URL（以 http:// 或 https:// 开头）")
            else:
                add_account(new_name.strip(), new_url.strip())
                st.success(f"✅ 账号「{new_name}」已保存！")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 当前账号列表")
    df_accounts = load_accounts()
    if df_accounts.empty:
        st.info("暂无监控账号，请在上方添加。")
    else:
        for _, row in df_accounts.iterrows():
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                st.text(str(row["id"]))
            with c2:
                st.markdown(f"**{row['name']}**  \n{row['url']}")
            with c3:
                if st.button("🗑️ 删除", key=f"del_{row['id']}"):
                    delete_account(int(row["id"]))
                    st.warning("已删除该账号及其关联笔记。")
                    time.sleep(0.5)
                    st.rerun()
            st.markdown("---")
