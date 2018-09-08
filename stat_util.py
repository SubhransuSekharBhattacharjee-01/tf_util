import numpy as np
from scipy.stats import invwishart, dirichlet, multivariate_normal
from cvxopt import spmatrix, amd
import chompack as cp
from Bron_Kerbosch.bronker_bosch3 import bronker_bosch3
from Bron_Kerbosch.reporter import Reporter

def get_sampler_func(dist, D):
    if (dist['family'] == 'uniform'):
        a = dist['a'];
        b = dist['b'];
        return lambda : np.random.uniform(a,b,(D,));

    elif (dist['family'] == 'uniform_int'):
        a = dist['a'];
        b = dist['b'];
        return lambda : np.random.randint(a,b+1,());

    elif (dist['family'] == 'multivariate_normal'):
        mu = dist['mu'];
        Sigma = dist['Sigma'];
        return lambda : np.random.multivariate_normal(mu, Sigma);

    elif (dist['family'] == 'isotropic_normal'):
        mu = dist['mu'];
        scale = dist['scale'];
        Sigma = scale*np.eye(D);
        dist = {'family':'multivariate_normal', 'mu':mu, 'Sigma':Sigma};
        return get_sampler_func(dist, D);

    elif (dist['family'] == 'truncated_normal'):
        mu = dist['mu'];
        Sigma = dist['Sigma'];
        L = np.linalg.cholesky(Sigma);
        return lambda : truncated_multivariate_normal_fast_rvs(mu, L);

    elif (dist['family'] == 'isotropic_truncated_normal'):
        mu = dist['mu'];
        scale = dist['scale'];
        Sigma = scale*np.eye(D);
        dist = {'family':'truncated_normal', 'mu':mu, 'Sigma':Sigma};
        return get_sampler_func(dist, D);

    elif (dist['family'] == 'inv_wishart'):
        df = dist['df'];
        Psi = dist['Psi'];
        iw = invwishart(df=df, scale=Psi);
        return lambda : iw.rvs(1);

    elif (dist['family'] == 'isotropic_inv_wishart'):
        df_fac = dist['df_fac'];
        df = df_fac*D;
        Psi = df*np.eye(D);
        dist = {'family':'inv_wishart', 'df':df, 'Psi':Psi};
        return get_sampler_func(dist, D);

    elif (dist['family'] == 'iso_mvn_and_iso_iw'):
        mu = dist['mu'];
        scale = dist['scale']
        dist_iso_mvn = {'family':'isotropic_normal', 'mu':mu, 'scale':scale}
        df_fac = dist['df_fac'];
        dist_iso_iw = {'family':'isotropic_inv_wishart', 'df_fac':df_fac};
        iso_mvn_sampler = get_sampler_func(dist_iso_mvn, D);
        iso_iw_sampler = get_sampler_func(dist_iso_iw, D);
        return lambda : (iso_mvn_sampler(), iso_iw_sampler());

    elif (dist['family'] == 'ui_and_iso_iw'):
        a = dist['a'];
        b = dist['b'];
        dist_ui = {'family':'uniform_int', 'a':a, 'b':b}
        df_fac = dist['df_fac'];
        dist_iso_iw = {'family':'isotropic_inv_wishart', 'df_fac':df_fac};
        ui_sampler = get_sampler_func(dist_ui, dist['ui_dim']);
        iso_iw_sampler = get_sampler_func(dist_iso_iw, dist['iw_dim']);
        return lambda : (ui_sampler(), iso_iw_sampler());

def get_density_func(dist, D):
    if (dist['family'] == 'uniform'):
        a = dist['a'];
        b = dist['b'];
        return lambda : np.power(1.0 / (b-a), D);

    elif (dist['family'] == 'uniform_int'):
        a = dist['a'];
        b = dist['b'];
        return lambda : 1.0 / (b-a);

    elif (dist['family'] == 'multivariate_normal'):
        mu = dist['mu'];
        Sigma = dist['Sigma'];
        mvn = multivariate_normal(mu, Sigma);
        return lambda x : mvn.pdf(x);

    elif (dist['family'] == 'isotropic_normal'):
        mu = dist['mu'];
        scale = dist['scale'];
        Sigma = scale*np.eye(D);
        dist = {'family':'multivariate_normal', 'mu':mu, 'Sigma':Sigma};
        return get_density_func(dist, D);

    elif (dist['family'] == 'truncated_normal'):
        mu = dist['mu'];
        Sigma = dist['Sigma'];
        dist = {'family':'multivariate_normal', 'mu':mu, 'Sigma':Sigma};
        return get_density_func(dist, D);

    elif (dist['family'] == 'isotropic_truncated_normal'):
        mu = dist['mu'];
        scale = dist['scale'];
        Sigma = scale*np.eye(D);
        dist = {'family':'multivariate_normal', 'mu':mu, 'Sigma':Sigma};
        return get_density_func(dist, D);

    elif (dist['family'] == 'inv_wishart'):
        df = dist['df'];
        Psi = dist['Psi'];
        iw = invwishart(df=df, scale=Psi);
        return lambda x : iw.pdf(x);

    elif (dist['family'] == 'isotropic_inv_wishart'):
        df_fac = dist['df_fac'];
        df = df_fac*D;
        Psi = df*np.eye(D);
        dist = {'family':'inv_wishart', 'df':df, 'Psi':Psi};
        return get_density_func(dist, D);

    elif (dist['family'] == 'iso_mvn_and_iso_iw'):
        mu = dist['mu'];
        scale = dist['scale']
        dist_iso_mvn = {'family':'isotropic_normal', 'mu':mu, 'scale':scale}
        df_fac = dist['df_fac'];
        dist_iso_iw = {'family':'isotropic_inv_wishart', 'df_fac':df_fac};
        iso_mvn_pdf = get_density_func(dist_iso_mvn, D);
        iso_iw_pdf = get_density_func(dist_iso_iw, D);
        return lambda x, y : iso_mvn_pdf(x)*iso_iw_pdf(y);

    elif (dist['family'] == 'ui_and_iso_iw'):
        a = dist['a'];
        b = dist['b'];
        dist_ui = {'family':'uniform_int', 'a':a, 'b':b}
        df_fac = dist['df_fac'];
        dist_iso_iw = {'family':'isotropic_inv_wishart', 'df_fac':df_fac};
        ui_pdf = get_density_func(dist_ui, dist['ui_dim']);
        iso_iw_pdf = get_density_func(dist_iso_iw, dist['iw_dim']);
        return lambda x, y : ui_pdf(x)*iso_iw_pdf(y);


def get_dist_str(dist):
    if (dist['family'] == 'uniform'):
        a = dist['a'];
        b = dist['b'];
        return 'u_%.1fto%.1f' % (a,b);

    elif (dist['family'] == 'uniform_int'):
        a = dist['a'];
        b = dist['b'];
        return 'ui_%dto%d' % (a,b);

    elif (dist['family'] == 'multivariate_normal'):
        mu = dist['mu'];
        Sigma = dist['Sigma'];
        return 'mvn'

    elif (dist['family'] == 'isotropic_normal'):
        mu = dist['mu'];
        scale = dist['scale'];
        return 'in_s=%.3f' % scale;

    elif (dist['family'] == 'truncated_normal'):
        mu = dist['mu'];
        scale = dist['scale'];
        return 'tn';

    elif (dist['family'] == 'isotropic_truncated_normal'):
        mu = dist['mu'];
        scale = dist['scale'];
        return 'itn_s=%.2f' % scale;

    elif (dist['family'] == 'inv_wishart'):
        df = dist['df'];
        Psi = dist['Psi'];
        iw = invwishart(df=df, scale=Psi);
        return 'iw'

    elif (dist['family'] == 'isotropic_inv_wishart'):
        df_fac = dist['df_fac'];
        return 'iiw_%d' % df_fac;

    elif (dist['family'] == 'iso_mvn_and_iso_iw'):
        mu = dist['mu'];
        scale = dist['scale']
        dist_iso_mvn = {'family':'isotropic_normal', 'mu':mu, 'scale':scale}
        df_fac = dist['df_fac'];
        dist_iso_iw = {'family':'isotropic_inv_wishart', 'df_fac':df_fac};
        return '%s_%s' % (get_dist_str(dist_iso_mvn), get_dist_str(dist_iso_iw));

    elif (dist['family'] == 'ui_and_iso_iw'):
        a = dist['a'];
        b = dist['b'];
        dist_ui = {'family':'uniform_int', 'a':a, 'b':b}
        df_fac = dist['df_fac'];
        dist_iso_iw = {'family':'isotropic_inv_wishart', 'df_fac':df_fac};
        return '%s_%s' % (get_dist_str(dist_ui), get_dist_str(dist_iso_iw));

def drawPoissonRates(D, ratelim):
    return np.random.uniform(0.1, ratelim, (D,));

def drawPoissonCounts(z, N):
    D = z.shape[0];
    x = np.zeros((D,N));
    for i in range(D):
        x[i,:] = np.random.poisson(z[i], (N,));
    return x;

def truncated_multivariate_normal_fast_rvs(mu, L):
    D = mu.shape[0];
    rejected = True;
    count = 1;
    while (rejected):
        z0 = np.random.normal(0,1,(D));
        z = np.dot(L, z0) + mu;
        rejected = 1 - np.prod((np.sign(z)+1)/2);
        count += 1;
    return z;

def truncated_multivariate_normal_rvs(mu, Sigma):
    D = mu.shape[0];
    L = np.linalg.cholesky(Sigma);
    rejected = True;
    count = 1;
    while (rejected):
        z0 = np.random.normal(0,1,(D));
        z = np.dot(L, z0) + mu;
        rejected = 1 - np.prod((np.sign(z)+1)/2);
        count += 1;
    return z;

def cov_error(V,I,J,Sigma):
    num_elems = len(V);
    error = 0.0;
    for i in range(num_elems):
        error += np.square(V[i] - Sigma[I[i], J[i]]);
    return error;

def get_GP_Sigma(tau, T, Ts):
    K = np.zeros((T, T));
    for i in range(T):
        for j in range(i,T):
            diff = (i-j)*Ts;
            K[i,j] = np.exp(-(np.abs(diff)**2) / (2*(tau**2)));
            if (i != j):
                K[j,i] = K[i,j];
    return K;

def get_S_D_graph(x, D, T):
    I = [];
    J = [];
    for t in range(T):
        for d in range(D):
            new_inds_Dblock = list(range(t*D+d,(t+1)*D))
            new_inds_temporal = list(range((t+1)*D+d, D*T, D));
            num_inds = len(new_inds_Dblock) + len(new_inds_temporal);
            I = I + new_inds_Dblock + new_inds_temporal;
            J = J + num_inds*[t*D+d];
    total_inds = len(I);
    V = [];
    for i in range(total_inds):
        V.append(x[I[i], J[i]]);
        
    num_nodes = D*T;
    NODES = list(range(num_nodes));
    NEIGHBORS = [];
    for i in range(num_nodes):
        NEIGHBORS.append([]);
    it = 0;
    for i in NODES:
        while (it < total_inds):
            if (J[it] == i):
                if (I[it] == i):
                    pass;
                else:
                    NEIGHBORS[i].append(I[it]);
                    NEIGHBORS[I[it]].append(i);
                it += 1;
            else:
                break;
    return V,I,J,NODES,NEIGHBORS;

def get_S_D_covariance(Sigma_D, taus, T, Ts):
    D = Sigma_D.shape[0];
    autocovariances = np.zeros((D, T));
    Sigma = np.zeros((D*T,D*T));
    for i in range(D):
        Sigma_tau_i = get_GP_Sigma(taus[i], T, Ts);
        autocovariances[i,:] = Sigma_D[i,i]*Sigma_tau_i[0,:];
    
    for t1 in range(T):
        t1_ind1 = int(t1*D);
        t1_ind2 = int((t1+1)*D);
        Sigma[t1_ind1:t1_ind2,t1_ind1:t1_ind2,] = Sigma_D;
        for t2 in range(t1+1,T):
            tau_mat = np.diag(autocovariances[:,t2-t1]);
            t2_ind1 = int(t2*D);
            t2_ind2 = int((t2+1)*D);
            Sigma[t1_ind1:t1_ind2, t2_ind1:t2_ind2] = tau_mat;
            Sigma[t2_ind1:t2_ind2, t1_ind1:t1_ind2,] = tau_mat;
        
    return Sigma;

def get_S_D_ME_covariance(Sigma_D, taus, T, Ts):
    Sigma = get_S_D_covariance(Sigma_D, taus, T, Ts);
    D = Sigma_D.shape[0];
    V,I,J,NODES,NEIGHBORS = get_S_D_graph(Sigma, D, T);
    report = Reporter('## bron_kerbosch')
    bronker_bosch3([], set(NODES), set(), report, NEIGHBORS)
    cliques = report.cliques;

    num_cliques = len(cliques);
    for i in range(num_cliques):
        cliques[i] = np.array(cliques[i]);

    R = Sigma;
    R_invs = [];
    for t in range(num_cliques):
        clique_t = cliques[t];
        R_t = R[np.expand_dims(clique_t, 1),clique_t];
        R_invs.append(np.linalg.inv(R_t));

    # algorithm 1 (Speed and Kiiveri)
    Sigma = np.eye(D*T);
    max_iters = 10000;
    errors = np.zeros((max_iters,));
    for it in range(max_iters):
        for t in range(num_cliques):
            clique_t = cliques[t];
            Sigma_t = Sigma[np.expand_dims(clique_t, 1),clique_t];
            
            Sigma_inv = np.linalg.inv(Sigma);
            Sigma_t_inv = np.linalg.inv(Sigma_t);
            update_t = R_invs[t] - Sigma_t_inv;
            
            Sigma_inv[np.expand_dims(clique_t, 1), clique_t] += update_t;
            Sigma = np.linalg.inv(Sigma_inv);
        error_it = cov_error(V,I,J,Sigma);
        if (error_it < 1e-10):
            break;
        errors[it] = error_it;

    converged = it < max_iters;
    return Sigma, converged;
    


