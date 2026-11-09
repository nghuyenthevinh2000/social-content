import { IonApp, IonRouterOutlet, setupIonicReact } from '@ionic/react';
import { IonReactRouter } from '@ionic/react-router';
import React from 'react';
import { Route } from 'react-router-dom';

import Home from './pages/Home';

/* Core CSS required for Ionic components to work properly */
import '@ionic/react/css/core.css';

/* Basic CSS for apps built with Ionic */
import '@ionic/react/css/normalize.css';
import '@ionic/react/css/structure.css';
import '@ionic/react/css/typography.css';

/* Optional CSS utils that can be commented out */
import '@ionic/react/css/padding.css';
import '@ionic/react/css/float-elements.css';
import '@ionic/react/css/text-alignment.css';
import '@ionic/react/css/text-transformation.css';
import '@ionic/react/css/flex-utils.css';
import '@ionic/react/css/display.css';

/* Theme variables */
import './theme/variables.css';

setupIonicReact();

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 32, textAlign: 'center', fontFamily: 'system-ui' }}>
          <h2>Đã xảy ra lỗi hiển thị</h2>
          <p style={{ color: '#666', margin: '12px 0 20px' }}>{this.state.error?.message}</p>
          <button
            style={{
              padding: '10px 18px',
              borderRadius: 12,
              border: '1px solid #ddd',
              background: '#fff',
              cursor: 'pointer',
              fontWeight: 600,
            }}
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.href = '/';
            }}
          >
            Tải lại ứng dụng
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const App: React.FC = () => (
  <IonApp>
    <ErrorBoundary>
      <IonReactRouter>
        <IonRouterOutlet>
          <Route path="/home" element={<Home />} />
          <Route path="/" element={<Home />} />
        </IonRouterOutlet>
      </IonReactRouter>
    </ErrorBoundary>
  </IonApp>
);

export default App;
