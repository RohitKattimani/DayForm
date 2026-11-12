import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  ArrowDownUp,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  Database,
  Headphones,
  Heart,
  Leaf,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  Minus,
  PackageCheck,
  Plus,
  Radio,
  RefreshCw,
  Search,
  SearchCode,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Star,
  Trash2,
  Truck,
  X,
  Zap,
} from 'lucide-react'

const API = ''
const money = (paise = 0) => `₹${Math.round(Number(paise) / 100).toLocaleString('en-IN')}`
const makeSessionId = () => {
  const existing = localStorage.getItem('dayform-session')
  if (existing) return existing
  const created = `guest-${window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`
  localStorage.setItem('dayform-session', created)
  return created
}

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`)
  return data
}

const fallbackCategories = ['All pieces', 'Audio & Tech', 'Home & Living', 'Carry & Wear', 'Care & Wellness']

function App() {
  const [sessionId] = useState(makeSessionId)
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState(fallbackCategories.slice(1))
  const [cities, setCities] = useState([])
  const [cart, setCart] = useState({ items: [], item_count: 0, subtotal_paise: 0 })
  const [health, setHealth] = useState(null)
  const [ops, setOps] = useState(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All pieces')
  const [city, setCity] = useState('All cities')
  const [sort, setSort] = useState('featured')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [inStockOnly, setInStockOnly] = useState(false)
  const [searchMeta, setSearchMeta] = useState(null)
  const [searchState, setSearchState] = useState('loading')
  const [searchError, setSearchError] = useState('')
  const [cartOpen, setCartOpen] = useState(false)
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [checkout, setCheckout] = useState({ name: '', email: '', phone: '', address: '', city: 'Bengaluru' })
  const [placingOrder, setPlacingOrder] = useState(false)
  const [order, setOrder] = useState(null)
  const [toast, setToast] = useState('')
  const [loadingCart, setLoadingCart] = useState(false)
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)
  const [showOps, setShowOps] = useState(false)

  const notify = useCallback((message) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 3000)
  }, [])

  const loadCart = useCallback(async () => {
    try {
      const data = await request(`/api/cart/${encodeURIComponent(sessionId)}`)
      setCart(data)
    } catch (error) {
      console.error('Cart load failed:', error)
    }
  }, [sessionId])

  const loadHealth = useCallback(async () => {
    try {
      const [serviceHealth, overview] = await Promise.all([
        request('/api/health'),
        request('/api/ops/overview'),
      ])
      setHealth(serviceHealth)
      setOps(overview)
    } catch (error) {
      setHealth({ services: {} })
      console.error('Service check failed:', error)
    }
  }, [])

  useEffect(() => {
    let alive = true
    request('/api/catalog')
      .then((data) => {
        if (!alive) return
        setProducts(data.items || [])
        setCategories(data.categories || fallbackCategories.slice(1))
        setCities(data.cities || [])
        setSearchState('ready')
      })
      .catch((error) => {
        if (!alive) return
        setSearchState('error')
        setSearchError(error.message)
      })
    loadCart()
    loadHealth()
    const poll = window.setInterval(loadHealth, 10000)
    return () => {
      alive = false
      window.clearInterval(poll)
    }
  }, [loadCart, loadHealth])

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      const params = new URLSearchParams()
      if (query.trim()) params.set('q', query.trim())
      if (category !== 'All pieces') params.set('category', category)
      if (city !== 'All cities') params.set('city', city)
      if (minPrice !== '') params.set('min_price', minPrice)
      if (maxPrice !== '') params.set('max_price', maxPrice)
      if (inStockOnly) params.set('in_stock', 'true')
      if (sort !== 'featured') params.set('sort', sort)
      setSearchState('loading')
      try {
        const data = await request(`/api/search?${params.toString()}`)
        setProducts(data.items || [])
        setSearchMeta(data)
        setSearchError('')
        setSearchState('ready')
      } catch (error) {
        setSearchError(error.message)
        setSearchState('error')
      }
    }, 260)
    return () => window.clearTimeout(timer)
  }, [query, category, city, sort, minPrice, maxPrice, inStockOnly])


  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        document.getElementById('product-search')?.focus()
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  useEffect(() => {
    if (!order || order.status === 'CONFIRMED') return undefined
    let attempts = 0
    const timer = window.setInterval(async () => {
      attempts += 1
      try {
        const updated = await request(`/api/orders/${order.order_number}`)
        setOrder((current) => ({ ...current, ...updated }))
      } catch (error) {
        console.warn('Order status refresh:', error)
      }
      if (attempts >= 20) window.clearInterval(timer)
    }, 1500)
    return () => window.clearInterval(timer)
  }, [order?.order_number, order?.status])

  const addToCart = async (product) => {
    try {
      const data = await request(`/api/cart/${encodeURIComponent(sessionId)}`, {
        method: 'POST', body: JSON.stringify({ product_id: product.id, quantity: 1 }),
      })
      setCart(data)
      notify(`${product.name} added to your bag`)
    } catch (error) {
      notify(error.message)
    }
  }

  const changeQuantity = async (item, quantity) => {
    if (quantity < 1) return removeItem(item)
    setLoadingCart(true)
    try {
      const data = await request(`/api/cart/${encodeURIComponent(sessionId)}/${item.id}`, {
        method: 'PATCH', body: JSON.stringify({ quantity }),
      })
      setCart(data)
    } catch (error) {
      notify(error.message)
      loadCart()
    } finally {
      setLoadingCart(false)
    }
  }

  const removeItem = async (item) => {
    setLoadingCart(true)
    try {
      const data = await request(`/api/cart/${encodeURIComponent(sessionId)}/${item.id}`, { method: 'DELETE' })
      setCart(data)
    } catch (error) {
      notify(error.message)
    } finally {
      setLoadingCart(false)
    }
  }

  const placeOrder = async (event) => {
    event.preventDefault()
    setPlacingOrder(true)
    try {
      const result = await request('/api/orders', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, ...checkout }),
      })
      setOrder(result)
      setCheckoutOpen(false)
      setCartOpen(false)
      setCart({ items: [], item_count: 0, subtotal_paise: 0 })
      loadHealth()
      notify('Your order is in the event pipeline')
    } catch (error) {
      notify(error.message)
      loadCart()
    } finally {
      setPlacingOrder(false)
    }
  }

  const activeServiceCount = useMemo(
    () => Object.values(health?.services || {}).filter((service) => service.status === 'connected').length,
    [health],
  )

  const statusLabel = (service) => {
    if (!service) return 'Checking'
    if (service.status === 'connected') return 'Connected'
    if (service.status === 'error') return 'Needs attention'
    return 'Add credentials'
  }

  const scrollToProducts = () => document.getElementById('collection')?.scrollIntoView({ behavior: 'smooth' })

  return (
    <div className="app-shell">
      <div className="announcement-bar">
        <span>THE GOOD THINGS, DELIVERED</span>
        <span className="announcement-center"><Sparkles size={12} /> Complimentary delivery on orders over ₹999</span>
        <span className="announcement-right">Thoughtful finds. Everyday prices.</span>
      </div>

      <header className="site-header">
        <div className="header-inner">
          <a className="brand-lockup" href="#top" aria-label="Dayform home">
            <span className="brand-mark"><span /></span>
            <span className="brand-name">dayform<span>.</span></span>
          </a>
          <nav className="main-nav" aria-label="Main navigation">
            <button onClick={() => { setCategory('All pieces'); scrollToProducts() }}>Shop all</button>
            <button onClick={() => { setCategory('Home & Living'); scrollToProducts() }}>Home</button>
            <button onClick={() => { setCategory('Audio & Tech'); scrollToProducts() }}>Tech</button>
            <button onClick={() => { setCategory('Carry & Wear'); scrollToProducts() }}>Style</button>
          </nav>
          <div className="header-actions">
            <button className="icon-button search-jump" aria-label="Jump to search" onClick={() => document.getElementById('product-search')?.focus()}><Search size={19} strokeWidth={1.8} /></button>
            <button className="bag-button" onClick={() => { setCartOpen(true); setCheckoutOpen(false) }} aria-label={`Open bag, ${cart.item_count} items`}>
              <ShoppingBag size={18} strokeWidth={1.8} /><span>Bag</span><b>{cart.item_count}</b>
            </button>
          </div>
        </div>
      </header>

      <main id="top">
        <section className="hero-section page-width">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-line" /> THE EVERYDAY EDIT · VOL. 01</div>
            <h1>Good things.<br /><em>Better</em> everyday.</h1>
            <p className="hero-description">A considered collection of things that make the everyday feel a little more extraordinary. Made to be lived with, loved for longer.</p>
            <div className="hero-buttons">
              <button className="button button-dark" onClick={scrollToProducts}>Explore the edit <ArrowUpRight size={16} /></button>
              <span className="hero-note"><span className="tiny-star">✳</span> Curated for real life</span>
            </div>
            <div className="hero-proof">
              <div className="avatar-stack"><span>R</span><span>A</span><span>M</span><span>+</span></div>
              <div><strong>4.8/5</strong><span className="proof-stars">★★★★★</span><small>Loved by 2,400+ everyday people</small></div>
            </div>
          </div>
          <div className="hero-art">
            <img className="hero-image" src="https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=1500&q=90" alt="A thoughtfully styled warm, minimal living space" />
            <div className="hero-image-shade" />
            <div className="hero-art-tag"><span className="tag-dot" /> A slower kind of shopping</div>
            <div className="hero-art-caption"><span>01 / 04</span><span>Objects with a point of view</span></div>
            <div className="floating-note"><Leaf size={15} /><span>Thoughtfully<br />picked, always.</span></div>
          </div>
        </section>

        <section className="promise-strip page-width" aria-label="Store promises">
          <div><Truck size={18} /><span>Free delivery over ₹999</span></div>
          <i />
          <div><ShieldCheck size={18} /><span>Secure, simple checkout</span></div>
          <i />
          <div><RefreshCw size={17} /><span>Easy 7-day returns</span></div>
          <i />
          <div><Heart size={17} /><span>Picked with intention</span></div>
        </section>

        <section className="collection-section page-width" id="collection">
          <div className="section-heading">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" /> THE COLLECTION</div>
              <h2>Find your <em>favourite</em> thing.</h2>
              <p>Little upgrades. Long-term favourites. All in one place.</p>
            </div>
            <div className="collection-aside"><span className="collection-count">{searchMeta?.total ?? products.length} pieces</span><span>·</span><span>Thoughtfully selected</span></div>
          </div>

          <div className="discovery-toolbar">
            <div className="category-tabs">
              <button className={category === 'All pieces' ? 'active' : ''} onClick={() => setCategory('All pieces')}>All pieces</button>
              {categories.map((item) => <button key={item} className={category === item ? 'active' : ''} onClick={() => setCategory(item)}>{item}</button>)}
            </div>
            <div className="discovery-controls">
              <label className="search-box" htmlFor="product-search"><Search size={17} /><input id="product-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search the good stuff…" /><kbd>⌘ K</kbd></label>
              <button className={`filter-toggle ${mobileFiltersOpen ? 'is-open' : ''}`} onClick={() => setMobileFiltersOpen((current) => !current)}><SlidersHorizontal size={16} /> Filters <ChevronDown size={14} /></button>
            </div>
          </div>

          {mobileFiltersOpen && <div className="filter-panel">
            <label>Delivering to <select value={city} onChange={(event) => setCity(event.target.value)}><option>All cities</option>{cities.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Sort by <select value={sort} onChange={(event) => setSort(event.target.value)}><option value="featured">Featured</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option><option value="rating">Top rated</option></select></label>
            <label>Min ₹ <input className="price-filter" type="number" min="0" placeholder="0" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} /></label>
            <label>Max ₹ <input className="price-filter" type="number" min="0" placeholder="Any" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} /></label>
            <label className="stock-check"><input type="checkbox" checked={inStockOnly} onChange={(event) => setInStockOnly(event.target.checked)} /> In stock only</label>
            <button className="clear-filters" onClick={() => { setCity('All cities'); setSort('featured'); setMinPrice(''); setMaxPrice(''); setInStockOnly(false); setQuery(''); setCategory('All pieces') }}>Clear all</button>
          </div>}

          <div className="search-context">
            <span>{query ? <>Results for <strong>“{query}”</strong></> : category === 'All pieces' ? 'Made for the everyday' : category}</span>
            <span className="search-source"><span className={`source-pulse ${searchMeta?.source ? 'live' : ''}`} /> {searchMeta?.source || 'Search index'} {searchMeta?.took_ms != null && <small>· {searchMeta.took_ms} ms</small>}</span>
          </div>

          {searchState === 'loading' && products.length === 0 ? <div className="product-grid skeleton-grid">{[1, 2, 3, 4].map((item) => <div className="skeleton-card" key={item}><div /><span /><span /></div>)}</div> : null}
          {searchState === 'error' && searchError && <div className="inline-alert"><SearchCode size={18} /><div><strong>Search service needs a connection</strong><span>{searchError}. Your catalogue is still visible; configure Aiven OpenSearch to enable live fuzzy search.</span></div></div>}

          {products.length > 0 ? <div className={`product-grid ${searchState === 'loading' ? 'is-refreshing' : ''}`}>
            {products.map((product, index) => <ProductCard key={product.id} product={product} index={index} onAdd={addToCart} />)}
          </div> : searchState !== 'loading' ? <div className="empty-results"><div className="empty-icon"><Search size={24} /></div><h3>No matches this time.</h3><p>Try a different word or clear a filter to see the full edit.</p><button className="button button-outline" onClick={() => { setQuery(''); setCategory('All pieces'); setCity('All cities'); setMinPrice(''); setMaxPrice(''); setInStockOnly(false) }}>Show all pieces <ArrowRight size={15} /></button></div> : null}

          <div className="collection-bottom"><span>Showing the good stuff, not all the stuff.</span><button onClick={() => { setCategory('All pieces'); setQuery(''); setCity('All cities'); setSort('featured'); setMinPrice(''); setMaxPrice(''); setInStockOnly(false) }}>View the full edit <ArrowRight size={15} /></button></div>
        </section>

        <section className="editorial-band page-width">
          <div className="editorial-image-wrap"><img src="https://images.unsplash.com/photo-1490312278390-ab64016e0aa9?auto=format&fit=crop&w=1200&q=85" alt="A calm, light-filled home interior" /></div>
          <div className="editorial-copy"><div className="eyebrow"><span className="eyebrow-line" /> A LITTLE MORE INTENTION</div><h2>Less, but<br /><em>lovelier.</em></h2><p>We believe the things around us should earn their place. So we look for considered design, everyday usefulness and details that make you smile.</p><button className="text-link" onClick={scrollToProducts}>Meet your next favourite <ArrowUpRight size={16} /></button><span className="editorial-number">DF / 001</span></div>
        </section>

        <section className="service-section page-width">
          <div className="service-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> THE ENGINE ROOM</div><h2>Good shopping.<br /><em>Good systems.</em></h2></div><div className="service-intro"><p>Behind every smooth checkout is a system that keeps its promises. Dayform runs on three live Aiven services, each with a job to do.</p><button className="ops-expand" onClick={() => setShowOps((current) => !current)}>{showOps ? 'Hide live signals' : 'View live signals'} <ArrowUpRight size={15} /></button></div></div>
          <div className="service-cards">
            <ServiceCard icon={<Database size={19} />} number="01" title="PostgreSQL" subtitle="The source of truth" service={health?.services?.postgresql} detail="Products, customer carts, orders and stock reservations live here. Row-level locks protect the last item at checkout." />
            <ServiceCard icon={<Radio size={19} />} number="02" title="Apache Kafka" subtitle="The event bloodstream" service={health?.services?.kafka} detail="An order is written to a transactional outbox, published to the store.events topic and consumed by the inventory worker." />
            <ServiceCard icon={<SearchCode size={19} />} number="03" title="OpenSearch" subtitle="Discovery, without the wait" service={health?.services?.opensearch} detail="The product index powers typo-tolerant search, category and city filters, stock filters and price sorting." />
          </div>
          {showOps && <div className="ops-console">
            <div className="ops-console-head"><div><span className="live-indicator" /> LIVE STORE TELEMETRY</div><span>REFRESHES EVERY 10 SEC</span></div>
            <div className="ops-metrics">
              <Metric label="Orders placed" value={ops?.metrics?.orders ?? '—'} icon={<ShoppingBag size={16} />} />
              <Metric label="Products indexed" value={ops?.metrics?.products ?? '—'} icon={<Search size={16} />} />
              <Metric label="Events consumed" value={ops?.metrics?.processed_events ?? '—'} icon={<Activity size={16} />} />
              <Metric label="Available units" value={ops?.metrics?.available_units ?? '—'} icon={<PackageCheck size={16} />} />
            </div>
            <div className="event-stream"><div className="event-stream-title"><span>RECENT EVENT STREAM</span><span>{ops?.events?.length || 0} records</span></div>
              {ops?.events?.length ? ops.events.map((event) => <div className="event-row" key={event.event_id}><span className="event-kind">{event.event_type}</span><span className="event-message">{event.message}</span><span className="event-status"><Check size={12} /> {event.status}</span></div>) : <div className="event-empty"><Radio size={16} /> Place a test order to see order.placed and inventory.updated events appear here.</div>}
            </div>
            <div className="ops-footnote"><LockKeyhole size={13} /> Credentials stay server-side. Checkout reservations and event processing are persisted in PostgreSQL.</div>
          </div>}
        </section>

        <section className="newsletter page-width"><div className="newsletter-mark"><Sparkles size={19} /></div><div><div className="eyebrow">A GOOD THING, OCCASIONALLY</div><h3>Make room for the <em>good stuff.</em></h3><p>New finds, useful ideas and little everyday upgrades. No noise.</p></div><button onClick={scrollToProducts}>Explore the edit <ArrowUpRight size={15} /></button></section>
      </main>

      <footer className="site-footer"><div className="footer-top"><a className="brand-lockup" href="#top"><span className="brand-mark"><span /></span><span className="brand-name">dayform<span>.</span></span></a><span>Considered things for everyday living.</span><a href="mailto:hello@dayform.store">Say hello <ArrowUpRight size={13} /></a></div><div className="footer-bottom"><span>© 2026 Dayform Market. Made for real life.</span><span>Built with care in India <span className="footer-heart">♥</span></span><span>PostgreSQL · Kafka · OpenSearch</span></div></footer>

      {cartOpen && <div className="overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) setCartOpen(false) }}>
        <aside className="cart-drawer" role="dialog" aria-modal="true" aria-label="Your shopping bag">
          <div className="drawer-header"><div><span className="eyebrow">YOUR DAYFORM EDIT</span><h2>{checkoutOpen ? 'A few details.' : 'Your bag.'}</h2></div><button className="close-button" onClick={() => { setCartOpen(false); setCheckoutOpen(false) }} aria-label="Close bag"><X size={20} /></button></div>
          {!checkoutOpen ? <>
            {cart.items.length ? <>
              <div className="drawer-items">{cart.items.map((item) => <div className="cart-line" key={item.id}><img src={item.product.image_url} alt={item.product.name} /><div className="cart-line-info"><span className="cart-line-category">{item.product.category}</span><strong>{item.product.name}</strong><span className="cart-line-price">{money(item.product.price_paise)}</span><div className="quantity-control"><button onClick={() => changeQuantity(item, item.quantity - 1)} aria-label="Decrease quantity"><Minus size={12} /></button><span>{item.quantity}</span><button onClick={() => changeQuantity(item, item.quantity + 1)} aria-label="Increase quantity"><Plus size={12} /></button></div></div><button className="remove-button" onClick={() => removeItem(item)} aria-label="Remove item"><Trash2 size={15} /></button></div>)}</div>
              <div className="drawer-bottom"><div className="delivery-note"><Truck size={16} /> {cart.subtotal_paise >= 99900 ? 'You unlocked complimentary delivery.' : `Add ${money(99900 - cart.subtotal_paise)} more for free delivery.`}</div><div className="subtotal-row"><span>Subtotal</span><strong>{money(cart.subtotal_paise)}</strong></div><div className="subtotal-row muted"><span>Delivery</span><span>{cart.subtotal_paise >= 99900 ? 'Complimentary' : money(4900)}</span></div><button className="button button-dark checkout-button" onClick={() => setCheckoutOpen(true)}>Continue to checkout <ArrowRight size={16} /></button><div className="secure-note"><LockKeyhole size={12} /> Secure checkout · Stock checked in real time</div></div>
            </> : <div className="empty-bag"><div className="empty-bag-icon"><ShoppingBag size={26} /></div><h3>Your bag is taking a breather.</h3><p>Find something lovely to bring home.</p><button className="button button-dark" onClick={() => setCartOpen(false)}>Explore the edit <ArrowRight size={15} /></button></div>}
          </> : <form className="checkout-form" onSubmit={placeOrder}>
            <button type="button" className="back-to-bag" onClick={() => setCheckoutOpen(false)}>← Back to your bag</button>
            <p className="form-intro">Where should we send your good things?</p>
            <label>Full name<input required minLength="2" value={checkout.name} onChange={(event) => setCheckout({ ...checkout, name: event.target.value })} placeholder="Your name" /></label>
            <label>Email address<input required type="email" value={checkout.email} onChange={(event) => setCheckout({ ...checkout, email: event.target.value })} placeholder="you@example.com" /></label>
            <label>Phone number<input required minLength="8" value={checkout.phone} onChange={(event) => setCheckout({ ...checkout, phone: event.target.value })} placeholder="+91 98765 43210" /></label>
            <label>Delivery address<textarea required minLength="8" value={checkout.address} onChange={(event) => setCheckout({ ...checkout, address: event.target.value })} placeholder="House / flat, street, area" rows="3" /></label>
            <label>City<input required value={checkout.city} onChange={(event) => setCheckout({ ...checkout, city: event.target.value })} placeholder="Bengaluru" /></label>
            <div className="checkout-total"><span>Order total</span><strong>{money(cart.subtotal_paise + (cart.subtotal_paise >= 99900 ? 0 : 4900))}</strong></div>
            <button className="button button-dark checkout-button" type="submit" disabled={placingOrder || !cart.items.length}>{placingOrder ? <><LoaderCircle className="spin" size={16} /> Placing order…</> : <>Place your order <ArrowRight size={16} /></>}</button>
            <div className="secure-note"><LockKeyhole size={12} /> Your order is saved before its event is published.</div>
          </form>}
        </aside>
      </div>}

      {order && <div className="overlay order-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) setOrder(null) }}><div className="order-modal" role="dialog" aria-modal="true" aria-label="Order confirmation"><button className="close-button order-close" onClick={() => setOrder(null)} aria-label="Close order confirmation"><X size={20} /></button><div className="order-success-icon"><CheckCircle2 size={30} /></div><div className="eyebrow">THAT'S A GOOD CHOICE</div><h2>{order.status === 'CONFIRMED' ? 'It’s official.' : 'You’re in good hands.'}</h2><p className="order-subtitle">Order <strong>{order.order_number}</strong> · {order.item_count || order.items?.reduce((sum, item) => sum + item.quantity, 0) || 0} items</p><div className="order-total-line"><span>Order total</span><strong>{money(order.total_paise)}</strong></div><div className="order-timeline"><div className="timeline-item done"><span><Check size={13} /></span><div><strong>Order saved</strong><small>PostgreSQL · Durable order record</small></div></div><div className={`timeline-item ${order.status === 'CONFIRMED' ? 'done' : 'active'}`}><span>{order.status === 'CONFIRMED' ? <Check size={13} /> : <LoaderCircle className="spin" size={13} />}</span><div><strong>Kafka event processed</strong><small>Inventory consumer updates stock safely</small></div></div><div className={`timeline-item ${order.status === 'CONFIRMED' ? 'done' : ''}`}><span>{order.status === 'CONFIRMED' ? <Check size={13} /> : <CircleDot size={13} />}</span><div><strong>Search index refreshed</strong><small>OpenSearch availability is in sync</small></div></div></div><div className={`order-status-banner ${order.status === 'CONFIRMED' ? 'confirmed' : ''}`}><span className="source-pulse live" />{order.status === 'CONFIRMED' ? 'Order confirmed · Inventory and search index updated' : 'Waiting for the Kafka consumer…'}</div><button className="button button-dark order-done" onClick={() => { setOrder(null); loadHealth() }}>Back to the good stuff <ArrowRight size={15} /></button></div></div>}

      {toast && <div className="toast-message"><CheckCircle2 size={16} /> {toast}</div>}
      <div className="service-health-pill" title={`${activeServiceCount} of 3 Aiven services connected`}><span className={`source-pulse ${activeServiceCount === 3 ? 'live' : ''}`} /> {activeServiceCount}/3 live services</div>
    </div>
  )
}

function ProductCard({ product, index, onAdd }) {
  const [saved, setSaved] = useState(false)
  const [adding, setAdding] = useState(false)
  const available = product.available_stock ?? Math.max(0, (product.stock_on_hand || 0) - (product.reserved_stock || 0))
  const handleAdd = async () => {
    setAdding(true)
    await onAdd(product)
    setAdding(false)
  }
  return <article className="product-card" style={{ '--card-index': index }}>
    <div className="product-image-wrap"><img src={product.image_url} alt={product.name} loading="lazy" /><div className="product-badge">{product.badge || product.brand}</div><button className={`save-product ${saved ? 'saved' : ''}`} aria-label={saved ? 'Remove from favourites' : 'Save to favourites'} onClick={() => setSaved((current) => !current)}><Heart size={17} fill={saved ? 'currentColor' : 'none'} /></button><button className="quick-add" disabled={available <= 0 || adding} onClick={handleAdd}>{adding ? <LoaderCircle className="spin" size={15} /> : available <= 0 ? 'Sold out' : <><Plus size={15} /> Add to bag</>}</button></div>
    <div className="product-meta"><span>{product.category}</span><span className="product-rating"><Star size={12} fill="currentColor" /> {Number(product.rating || 0).toFixed(1)} <small>({product.review_count || 0})</small></span></div>
    <div className="product-title-row"><h3>{product.name}</h3><strong>{money(product.price_paise)}</strong></div>
    <div className="product-bottom-row"><span>{product.city} dispatch</span><span className={available <= 5 ? 'low-stock' : ''}>{available <= 0 ? 'Out of stock' : available <= 5 ? `Only ${available} left` : 'In stock'}</span></div>
  </article>
}

function ServiceCard({ icon, number, title, subtitle, service, detail }) {
  const connected = service?.status === 'connected'
  const error = service?.status === 'error'
  return <article className="service-card"><div className="service-card-top"><span className="service-icon">{icon}</span><span className="service-number">{number} / 03</span></div><div className="service-card-copy"><h3>{title}</h3><span className="service-subtitle">{subtitle}</span><p>{detail}</p></div><div className="service-card-bottom"><span className={`service-status ${connected ? 'connected' : error ? 'error' : ''}`}><i />{connected ? 'Connected' : error ? 'Needs attention' : 'Awaiting setup'}</span><span className="service-status-detail">{service?.detail || 'Configure service credentials to activate'}</span></div></article>
}

function Metric({ label, value, icon }) {
  return <div className="metric-card"><span className="metric-icon">{icon}</span><div><strong>{value}</strong><small>{label}</small></div></div>
}

export default App
