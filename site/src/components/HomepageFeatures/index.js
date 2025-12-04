import React from 'react'
import clsx from 'clsx'
import styles from './styles.module.css'

const FeatureList = [
    {
        title: 'Real-Time Dashboard',
        image: require('./grafana-dashboard.png').default,
        alt: 'Grafana dashboard showing power consumption',
        description: (
            <>
                Monitor simulated vs actual power consumption in real-time through the Grafana dashboard. Track carbon
                emissions and identify prediction accuracy.
            </>
        ),
    },
    {
        title: 'REST API',
        image: require('./api-page.png').default,
        alt: 'OpenAPI documentation page',
        description: (
            <>
                Query simulation data and control topology through a documented REST API. Integrate OpenDT with your
                existing infrastructure and automation workflows.
            </>
        ),
    },
]

function Feature({ image, alt, title, description }) {
    return (
        <div className={clsx('col col--6')}>
            <div className={styles.featureImageWrapper}>
                <img src={image} alt={alt} className={styles.featureImage} />
            </div>
            <div className="text--center padding-horiz--md">
                <h3>{title}</h3>
                <p>{description}</p>
            </div>
        </div>
    )
}

export default function HomepageFeatures() {
    return (
        <section className={styles.features}>
            <div className="container">
                <div className={clsx('row', styles.featureRow)}>
                    {FeatureList.map((props, idx) => (
                        <Feature key={idx} {...props} />
                    ))}
                </div>
            </div>
        </section>
    )
}
