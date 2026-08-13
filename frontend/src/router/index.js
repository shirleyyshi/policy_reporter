import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/Login.vue'
import Home from '@/views/Home.vue'
import CentralEditor from '@/views/CentralEditor.vue'
import LocalEditor from '@/views/LocalEditor.vue'
import LegalEditor from '@/views/LegalEditor.vue'
import AgentRun from '@/views/AgentRun.vue'
import AgentRuns from '@/views/AgentRuns.vue'

const routes = [
    { path: '/', redirect: '/login' },  // 默认进入登录页
    { path: '/login', name: 'Login', component: Login },
    { path: '/home', name: 'Home', component: Home },
    { path: '/editor/central', name: 'CentralEditor', component: CentralEditor },
    { path: '/editor/local', name: 'LocalEditor', component: LocalEditor },
    { path: '/editor/legal', name: 'LegalEditor', component: LegalEditor },
    { path: '/agent', name: 'AgentRun', component: AgentRun },
    { path: '/agent/runs', name: 'AgentRuns', component: AgentRuns },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// 路由守卫：未登录则跳转登录页
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('access_token')
    if (to.path === '/login') {
        next()
    } else if (!token) {
        next('/login')
    } else {
        next()
    }
})

export default router



