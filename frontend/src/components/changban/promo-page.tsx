import Link from "next/link";

import "./promo-page.css";

const pillars = [
  {
    index: "01",
    title: "人即目的",
    text: "合作契约把企业的成长和个人的价值绑在一起。制度先问人要成为谁，再问怎么分结果。",
  },
  {
    index: "02",
    title: "数字灵魂",
    text: "英雄主义很脆。把销冠和业务骨干的隐性经验沉淀下来，组织才有不会离职的能力。",
  },
  {
    index: "03",
    title: "液态组织",
    text: "拆掉吃大锅饭的岗位墙。权力和利益流向真正创造价值的人，中后台变成前线的接口。",
  },
  {
    index: "04",
    title: "看见潜能",
    text: "怎么分钱，和往哪探索，是两件事。考核保护当下，目标保护试错，人才看冰山下面。",
  },
];

const practices = [
  {
    index: "启蒙",
    title: "把认知先校准",
    text: "给高管和人力资源团队讲清楚智能时代的组织逻辑，并在招聘、绩效、组织诊断这些真实场景里动手。",
  },
  {
    index: "陪跑",
    title: "走到最后一公里",
    text: "诊断现有流程，找出高耗时、低价值的环节，和团队一起把做法用起来，直到它变成肌肉记忆。",
  },
  {
    index: "定制",
    title: "留下企业自己的助手",
    text: "按企业的制度和知识，做招聘、政策问答、绩效分析这类专属智能体。技术服务于管理目标。",
  },
];

export function PromoPage() {
  return (
    <div className="cb">
      <header className="cb-nav">
        <a className="cb-mark" href="#top">
          长伴咨询
        </a>
        <nav>
          <a href="#pillars">基石</a>
          <a href="#practice">做法</a>
          <a href="#method">方法</a>
          <a href="#contact">联系</a>
          <Link href="/workspace">工作台</Link>
        </nav>
      </header>

      <main id="top">
        <section className="cb-hero">
          <p className="cb-spine" aria-hidden="true">
            Changban · the long companionship
          </p>
          <p className="cb-kicker">山西 · 组织、人才与激励</p>
          <h1>
            每个高成长企业背后，
            <br />
            都有长伴相随
          </h1>
          <p className="cb-lede">
            企业不是一台精密的赚钱机器，人也不是可以替换的零件。我们陪高成长公司，把组织、激励和经验设计成能自己生长的系统。
          </p>
          <a className="cb-seal" href="#contact" aria-label="预约一次对话">
            <span>长伴</span>
            <small>相随</small>
          </a>
          <ul className="cb-values">
            <li>洞察本质</li>
            <li>拥抱智能</li>
            <li>陪伴成长</li>
            <li>成就价值</li>
          </ul>
        </section>

        <section id="pillars" className="cb-section">
          <div className="cb-section-head">
            <p>四大基石</p>
            <h2>先把人看对，制度才站得住。</h2>
          </div>
          <ol>
            {pillars.map((item) => (
              <li key={item.index}>
                <span>{item.index}</span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section id="practice" className="cb-section cb-practice">
          <div className="cb-section-head">
            <p>怎么一起做</p>
            <h2>启蒙，陪跑，然后留下自己的能力。</h2>
          </div>
          <div className="cb-practice-grid">
            {practices.map((item) => (
              <article key={item.index}>
                <p>{item.index}</p>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="method" className="cb-method">
          <p>设计精益化</p>
          <blockquote>
            管理的最高境界，不是织一张更密的网，而是留出一片能生长的土壤。
          </blockquote>
          <div>
            <p>砍掉不促进业务增长、也不培养人的审批。每加一条制度，先问它是在帮忙，还是在添乱。</p>
            <p>利益公式要简单到当事人自己算得清。规则透明，人就不必把聪明用在对付制度上。</p>
          </div>
        </section>
      </main>

      <footer id="contact">
        <p>预约一次组织对话</p>
        <a href="mailto:wangjian@cbrlzy.com">wangjian@cbrlzy.com</a>
        <a href="tel:13233635522">132 3363 5522</a>
        <small>© {new Date().getFullYear()} 长伴咨询 · 山西长伴人力资源</small>
      </footer>
    </div>
  );
}
