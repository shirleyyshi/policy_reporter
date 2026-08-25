import { createRouter, createWebHistory } from 'vue-router'

// 路由懒加载：按需加载组件，减小首屏 bundle
const routes = [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') },
    { path: '/home', name: 'Home', component: () => import('@/views/Home.vue') },
    { path: '/editor/central', name: 'CentralEditor', component: () => import('@/views/CentralEditor.vue') },
    { path: '/editor/local', name: 'LocalEditor', component: () => import('@/views/LocalEditor.vue') },
    { path: '/policy/:source/:id', name: 'PolicyDetail', component: () => import('@/views/PolicyDetail.vue') },
    { path: '/editor/legal', name: 'LegalEditor', component: () => import('@/views/LegalEditor.vue') },
    { path: '/agent', name: 'AgentRun', component: () => import('@/views/AgentRun.vue') },
    { path: '/agent/runs', name: 'AgentRuns', component: () => import('@/views/AgentRuns.vue') },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// 路由守卫：未登录则跳转登录页
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('access_token')
    if (to.path === '/login' || to.path === '/register') {
        next()
    } else if (!token) {
        next('/login')
    } else {
        next()
    }
})

export default router
