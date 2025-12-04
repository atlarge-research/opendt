import React from 'react'
import clsx from 'clsx'
import styles from './styles.module.css'

const FeatureList = [
    {
        title: 'Power Prediction',
        Svg: () => (
            <img
                src={require('./screenshot-opendt.png').default}
                alt="Real-time power prediction dashboard"
            />
        ),
        description: (
            <>
                Compare simulated power consumption against actual measurements in real-time 
                using the Grafana dashboard.
            </>
        ),
    },
    {
        title: 'Active Calibration',
        Svg: () => (
            <img
                src={require('./screenshot-results.png').default}
                alt="Calibration results"
            />
        ),
        description: (
            <>
                Automatically tune simulation parameters to minimize prediction error 
                through grid search optimization.
            </>
        ),
    },
    {
        title: 'What-If Analysis',
        Svg: () => (
            <img
                src={require('./screenshot-explore.png').default}
                alt="Explore infrastructure changes"
            />
        ),
        description: (
            <>
                Test infrastructure changes without touching live hardware. 
                Modify topology and observe predicted impact.
            </>
        ),
    },
]

function Feature({ Svg, title, description }) {
    return (
        <div className={clsx('col col--4')}>
            <div className="text--center">
                <Svg className={styles.featureSvg} role="img" />
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
                <div className="row">
                    {FeatureList.map((props, idx) => (
                        <Feature key={idx} {...props} />
                    ))}
                </div>
            </div>
        </section>
    )
}
