export async function mountAppWhenRouterReady({ app, router, root = '#app' }) {
  await router.isReady()
  return app.mount(root)
}
