#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 24 13:43:28 2021

@author: minx
"""

from PAPER.tree_tools import *
import time
from random import choices
from igraph import *
import numpy as np
import collections
import scipy.optimize

from PAPER.estimateAlpha import *
import PAPER.grafting as grafting
import PAPER.seqnoise as seqnoise

def gibbsToConv(graf, DP=False, 
                K=1, 
                alpha=None, beta=None, 
                alpha0=50,
                talpha=None, tbeta=None, theta=None, eta=None,
                Burn=10, M=40, gap=1, 
                MAXITER=100, 
                tol=0.1, 
                size_thresh=0.01, birth_thresh=0.8,
                method="full",
                seq=False, timed=False, trace_id=None):
    """
    Run gibbs sampler to generate posterior root probs.
    

    Parameters
    ----------
    graf : igraph object
        Input graph. Converted to undirected graph with 
        no multi-edges. 
    DP : boolean, optional
        Use random K model or not. The default is False.
    K : int, optional
        Num of cluster-trees. Ignored if DP is True. The default is 1.
    alpha : float, optional
        Parameter. Set both alpha=0 and beta=0 (default) to 
        estimate the parameters via EM. The default is 0. 
    beta : float, optional
        Parameter. Set both alpha=0 and beta=0 (default) to estimate
        the parameter via EM. The default is 0.
    alpha0 : float, optional
        Initialization for parameter. Ignored if DP is False. The default is 50.
    Burn : int, optional
        Num of burn iteration. Unimportant if chain runs to 
        convergence. The default is 10.
    M : int, optional
        Num of iterations per convergence check. The default is 40.
    gap : int, optional
        Num of samples to skip for recording results. The default is 1.
    MAXITER : int, optional
        Maximum number of convergence checks. The default is 100.
    tol : float, optional
        Convergence threshold. The default is 0.1.
    size_thresh : float, optional
        Thresh for keeping a cluster-tree. 
        Ignored if K==1. The default is 0.01.
    birth_thresh : float, optional
        Thresh for creating new distinct cluster-tree 
        in output. 
        Ignored if K==1.
        The default is 0.8.
    method : string, optional
        Either "full" or "collapsed". The default is "full".
    burn_thresh : float, optional
        Criterion for determining whether burn in is
        complete. The default is 0.95.

    Returns
    -------
    0. nparray of posterior root probs
    1. first chain outputs
    2. second chain outputs

    """
    
    graf.to_undirected()
    graf.simplify()
    foo = graf.clusters().giant()
    if (len(foo.vs) < len(graf.vs)):
        print('Warning: input graph disconnected. \
              Taking largest connected component as the input graph. \
              Node ID may change as a result.')
        graf = foo
    
    n = len(graf.vs)
    m = len(graf.es)
    graf2 = graf.copy()
    
    if (alpha == None and beta == None and not seq):
        beta = 1
        alpha = estimateAlphaEM(graf, display=False)
        print("Estimated alpha as {0}".format(alpha))
    else:
        print("Using alpha {0} and beta {1}".format(alpha, beta))
    
    if (DP):
        print("Using random K model")
    else:
        print("Using fixed K={0} model".format(K))
        
    if (seq):
        print("Using sequential noise model")
    
    
    params = {"alpha" : alpha,
              "beta" : beta,
              "talpha" : talpha, "tbeta" : tbeta,
              "theta" : theta,
              "eta" : eta
              }
    
    options = {"Burn": Burn, "M": M, 
               "gap": gap, 
               "size_thresh": size_thresh,
               "birth_thresh": birth_thresh,
               "display": False,
               "timed" : timed,
               }    
    
    if (trace_id is not None):
        options["trace_id"] = trace_id
    
    
    if (DP and method == "full"):
        gibbsFn = gibbsFullDP
    if ((not DP) and method == "full"):
        gibbsFn = gibbsFull
        
        
    if (DP and method == "collapsed"):
        gibbsFn = grafting.gibbsGraftDP
    if ((not DP) and method== "collapsed"):
        gibbsFn = grafting.gibbsGraft
    
    if (seq):
        gibbsFn = seqnoise.gibbsFullSeq
    
    
    if (not DP):
        res = gibbsFn(graf, K=K, **params, **options)
        res1 = gibbsFn(graf2, K=K, **params, **options)
    else:
        res = gibbsFn(graf, alpha0=alpha0, **params, **options)
        res1 = gibbsFn(graf2, alpha0=alpha0, **params, **options)        


    all_outer_iters = []
    all_deviations = []    

    total_iter = M

    for i in range(MAXITER):
        
        allfreq = res["allfreq"]
        allfreq1 = res1["allfreq"]
        
        
        print(sum(allfreq))
            
        p1 = allfreq/sum(allfreq)
        p2 = allfreq1/sum(allfreq1)
        
        deviation = (1/2)*sum(np.abs( p1**(1/2) - p2**(1/2) )**2)
        print((i, deviation))
        
        all_outer_iters.append(total_iter)
        all_deviations.append(deviation)
        
        
        
        if (deviation < tol):
            break
        
        
        Mp = M*(i+1)
        total_iter = total_iter + Mp
        
        options["Burn"] = 0
        options["M"] = Mp
        
        options1 = options.copy()
        
        
        options["freq"] = res["freq"]
        options["node_tree_coo"] = res["node_tree_coo"]
        options1["freq"] = res1["freq"]
        options1["node_tree_coo"] = res1["node_tree_coo"]
        
        if (method=="full" or seq):
            options["pi"] = res["pi"]
            options1["pi"] = res1["pi"]   
        
        if (DP):
            options["tree2root"] = res["tree2root"]
            options1["tree2root"] = res1["tree2root"]
        
        
        
        if ( (not DP) and method=="full" and (not seq)):
            res = gibbsFn(graf, K=K,
                          **params, **options)
            res1 = gibbsFn(graf2, K=K,
                           **params, **options1)
            
        if ( (not DP) and method=="collapsed" and (not seq)):
            res = gibbsFn(graf, K=K, 
                          **params, **options)
            res1 = gibbsFn(graf2, K=K, 
                           **params, **options1)
            
        if (DP and method=="full"):
            res = gibbsFn(graf, alpha0=res["alpha0"],
                          **params, **options)
            res1 = gibbsFn(graf2, alpha0=res1["alpha0"], 
                           **params, **options1)    
            
        if (DP and method=="collapsed"):
            res = gibbsFn(graf, alpha0=res["alpha0"], 
                          **params, **options)
            res1 = gibbsFn(graf2, alpha0=res1["alpha0"], 
                           **params, **options1)
    
        if (seq):
            res = gibbsFn(graf, K=K,
                          **params, **options)
            res1 = gibbsFn(graf2, K=K, 
                           **params, **options1)
    
    
    allfreq = allfreq + allfreq1
    allfreq = allfreq/sum(allfreq)
    
    return((allfreq, res, res1, all_outer_iters, all_deviations))



def gibbsFull(graf, Burn=40, M=50, gap=1, alpha=0, beta=1, K=1, 
              display=True, size_thresh=0.01, birth_thresh=0.8,
              **options):
    """
    Full Gibbs sampler for computing posterior root prob and 
    node tree co-occurrence in fixed K setting. 

    Parameters
    ----------
    graf : igraph object
        Input graph.
    Burn : int, optional
        Num of burn in iterations. The default is 30.
    M : int, optional
        Num of regular iterations. The default is 50.
    gap : int, optional
        Num of samples to skip when recording results. 
        The default is 1.
    alpha : float, optional
        Parameter. The default is 0.
    beta : float, optional
        Parameter. The default is 1.
    K : int, optional
        Num of roots/clusters. The default is 1.
    display : boolean, optional
        Detailed display. The default is True.
    size_thresh : float, optional
        Thresh for keeping a cluster-tree. The default is 0.01.
    birth_thresh : float, optional
        Thresh for creating new distinct cluster-tree 
        in output. The default is 0.8.
    initpi : list, optional
        Initialization for ordering. The default is None.

    Returns
    -------
    0: nparray of posterior root probs
    1: dictionary mapping tree k to its posterior root probs
    2: nparray of node tree co-occurrence
    3: final roots (used for initiailization)
    4: final ordering (used for initialization)

    """
    n = len(graf.vs)
    m = len(graf.es)

    trace = [0] * int(M/gap)
    if ("trace_id" in options):
        trace_id = options["trace_id"]
    else:
        trace_id = 0


    if ("pi" in options):
        mypi = options["pi"]
        tree2root = mypi[0:K]
    else:
        wilsonTree(graf)
        v = choices(range(n))[0]
    
        countSubtreeSizes(graf, v)
        tree2root = [v]
        mypi = sampleOrdering(graf, tree2root, alpha, beta)

        for e in graf.es.select(_within =mypi[0:K]):
            e['tree'] = False


    if ("node_tree_coo" in options):
        node_tree_coo = options["node_tree_coo"]
    else:
        node_tree_coo = np.zeros((n, 0))
    
    
    if ("freq" in options):
        freq = options["freq"]
    else:   
        freq = {}
        if (K == 1):
            freq[0] = [0] * n

    timeA = 0
    timeB = 0
    
    for i in range(Burn + M):
        
        for v in tree2root:
            assert graf.vs[v]["pa"] is None        
        
        ##
        start = time.time()
        nodewiseSamplePA(graf, mypi, alpha=alpha, beta=beta, K=K)
        timeA = timeA + (time.time() - start)
                
        ##
        start = time.time()
        tree2root = mypi[0:K]
        mypi = sampleOrdering(graf, tree2root, alpha=alpha, beta=beta)
        
    
                
        ## sort and display sizes
        sizes = getTreeSizes(graf, tree2root)
        
        
        sizes_sorted = -np.sort( - np.array(sizes))
        sizes_args = np.argsort(- np.array(sizes) )
        
        if (display):
            print("iter {0}  sizes {1}".format(i, sizes_sorted))
        
        tree2root_sorted = [0] * len(tree2root)
        for k in range(len(tree2root)):
            tree2root_sorted[k] = tree2root[sizes_args[k]]
        
        """ record results """
        
        if (i >= Burn and i % gap == 0):
            
            if (K == 1):
                freq[0] = freq[0] + countAllHist(graf, tree2root[0])[0]
                #trace[i - Burn] = countAllHist(graf, tree2root[0])[0][trace_id]
            else:   
                node_tree_coo = updateInferResults(graf, freq, tree2root, 
                                                   alpha=alpha, beta=beta, 
                                                   size_thresh=size_thresh, 
                                                   birth_thresh=birth_thresh, 
                                                   node_tree_coo=node_tree_coo)
        timeB = timeB + (time.time() - start)
        
    allfreqs = np.array([0] * n)    
    
    for k in range(len(freq)):
        allfreqs = allfreqs + freq[k]
        
    allfreqs = allfreqs/sum(allfreqs)
    
    ##print([timeA, timeB])
    
    return( {"allfreq" : allfreqs,
            "freq" : freq, 
            "node_tree_coo" : node_tree_coo, 
            "tree2root" : tree2root, 
            "pi" : mypi,
            "trace" : trace})
        


def gibbsFullDP(graf, Burn=20, M=50, gap=1, alpha=0, beta=1, alpha0=50, 
                display=True, size_thresh=0.01, 
                birth_thresh=0.8, shatter_thresh=1,
                initpi=None, initroots=None, PY=False, **options):
    """
    Full Gibbs sampler for computing posterior root prob 
    in the random K setting.  

    Parameters
    ----------
    graf : igraph object
        Input graph.
    Burn : int, optional
        Num of burn in iterations. The default is 30.
    M : int, optional
        Num of regular iterations. The default is 50.
    gap : int, optional
        Num of samples to skip when recording results. 
        The default is 1.
    alpha : float, optional
        Parameter. The default is 0.
    beta : float, optional
        Parameter. The default is 1.
    alpha0 : float, optional
        Parameter. The default is 5.
    display : boolean, optional
        Detailed display. The default is True.
    size_thresh : float, optional
        Thresh for keeping a cluster-tree. The default is 0.01.
    birth_thresh : float, optional
        Thresh for creating new distinct cluster-tree 
        in output. The default is 0.8.
    initpi : list, optional
        Ordering initialization. The default is None.
    initroots : list, optional
        Root initialization. The default is None.

    Returns
    -------
    0. nparray of length n of posterior root prob
    1. dict giving posterior root prob for each distinct cluster-tree
    2. list of all Ks
    3. final set of roots (used for initialization)
    4. final alpha0 (used for initialization)
    5. final ordering (used for initialization)

    """
    
    if (alpha == None and beta == None):
        beta = 1
        alpha = estimateAlphaEM(graf, display=False)
        print("Estimated alpha as {0}".format(alpha))
    else:
        print("Using alpha {0} and beta {1}".format(alpha, beta))

    
    n = len(graf.vs)
    m = len(graf.es)
    
    
    if ("pi" in options):
        mypi = options["pi"]
        tree2root = options["tree2root"]
    else:
        wilsonTree(graf)
        v = choices(range(n))[0]
    
        countSubtreeSizes(graf, v)
        tree2root = [v]
    
        tmp = sampleOrdering(graf, tree2root, alpha, beta, DP=True)
        mypi = tmp[0]
        tree2root = tmp[1]

    
    if ("freq" in options):
        freq = options["freq"]
    else:
        freq = {}
        
    
    if ("node_tree_coo" in options):
        node_tree_coo = options["node_tree_coo"]
    else:
        node_tree_coo = np.zeros((n, 0))

    
    allK = []
    
    for i in range(Burn + M):
            
        tree2root = nodewiseSampleDP(graf, mypi, tree2root, alpha=alpha, beta=beta, alpha0=alpha0, PY=PY)

        K = len(tree2root)
        sizes = getTreeSizes(graf, tree2root)
        sizes_args = np.argsort( - np.array(sizes))
        sizes_sorted = -np.sort( - np.array(sizes))
    
        while (sizes_sorted[0] > shatter_thresh * n):
            big_root = tree2root[sizes_args[0]]
            ## find all direct children of big_root
            big_root_children = [v for v in graf.neighbors(big_root) if graf.vs[v]["pa"] == big_root]

            for v in big_root_children[1:]:
                graf.vs[v]["pa"] = None
                tree2root.append(v)
                ## get edge between v and big_root and set "tree" to False
                e = graf.get_eid(v, big_root)
                graf.es[e]["tree"] = False

            graf.vs[big_root_children[0]]["pa"] = None
            graf.vs[big_root]["pa"] = big_root_children[0]
            tree2root.append(big_root_children[0])
            tree2root.remove(big_root)

            ## count number of tree edges
            tree_edges = sum(graf.es["tree"])
            assert tree_edges == n - len(tree2root)

            sizes = getTreeSizes(graf, tree2root)
            sizes_args = np.argsort( - np.array(sizes))
            sizes_sorted = -np.sort( - np.array(sizes))

            if (display):
                print(f"new K: {len(tree2root)}")
                print(sizes)


        tmp = sampleOrdering(graf, tree2root, alpha=alpha, beta=beta, DP=True)
        mypi = tmp[0]
        tree2root = tmp[1]


        ## Uncomment to update alpha0
        alpha0tilde = drawAlpha0tilde(K, n, alpha0/(alpha+2*beta))
        alpha0 = alpha0tilde*(alpha+2*beta)
        
        if (PY):
            alpha0 = 1
        
        if (display):
            print("iter {0}  a0 {1}  K {2}  sizes{3}".format(i, round(alpha0, 3),
                                                             K, sizes_sorted[0:4]))
            
        """ record results """

        if (i >= Burn and i % gap == 0):
            allK.append(sum(sizes_sorted > (size_thresh * n)))
            
            node_tree_coo = updateInferResults(graf, freq, tree2root, 
                               alpha=alpha, beta=beta, 
                               size_thresh=size_thresh, 
                               node_tree_coo=node_tree_coo,
                               birth_thresh=birth_thresh)
            
            
    allfreqs = np.array([0] * n)
    tree_count = np.array( [0] * len(freq), dtype="f")
    for k in range(len(freq)):
        allfreqs = allfreqs + freq[k]
        tree_count[k] = sum(freq[k])
        
    return({"allfreq" : allfreqs, 
            "freq" : freq, 
            "allK" : allK, 
            "tree2root" : tree2root, 
            "tree_count" : tree_count,
            "alpha0" : alpha0, 
            "node_tree_coo" : node_tree_coo,
            "pi" : mypi})





def nodewiseSampleDP(graf, mypi, tree2root, alpha, beta, alpha0, PY=False):
    """
    Generates new forest for a given ordering by sampling
    a new parent for each node. Used in random K setting.

    Require: graf.es has "tree" attribute    

    Parameters
    ----------
    graf : igraph object
        Input graph; "tree" edge attribute and "pa" node
        attributes are modified in place.
    mypi : list
        Given ordering of the nodes.
    tree2root : list
        Lists of the roots for each of the trees.
    alpha : float
        Parameter.
    beta : float
        Parameter.
    alpha0 : float
        Parameter.

    Returns
    -------
    New list of roots

    """
    n = len(graf.vs)
    m = len(graf.es)
    n2 = n*(n-1)/2
    
    ## DEBUG
    getTreeSizes(graf, tree2root)
    
    root_dict = {}
    for v in tree2root:
        root_dict[v] = 1
        assert graf.vs[v]["pa"] == None
    
    mypi_inv = [0] * n
    for i in range(n):
        mypi_inv[mypi[i]] = i    
                
    all_tree_degs = getAllTreeDeg(graf)        
    assert sum(all_tree_degs) == 2*(n-len(tree2root))
    
    edge_ls = []
    curK = len(tree2root)
    for i in range(n-1):
       
        k = i + 1
        u = mypi[k]
        mypa = graf.vs[u]["pa"]
        uisroot = (mypa == None)
        
        nbs = graf.neighbors(u)
        nbs = [w for w in nbs if mypi_inv[w] < k]

        tree_degs = np.array([all_tree_degs[w] for w in nbs])
        root_adj = np.array([w in root_dict for w in nbs])
        pa_adj = np.array([w == mypa for w in nbs])
        
        tmp_p = beta*tree_degs + 2*beta*root_adj - beta*pa_adj + alpha
        new_root_wt = alpha0 * (m-n+curK+1-uisroot)/(n2-n+curK+1-uisroot) * \
            (beta*all_tree_degs[u] + beta*uisroot + alpha)/(beta+alpha)
        

        ## Pitman--Yor: new node becomes root with probability (beta s_{t-1} + alpha) / ( 2*beta*(t-1) + alpha*t)
        if (PY):
            tmp_p = beta*tree_degs + beta*root_adj - beta*pa_adj + alpha
            new_root_wt = (beta*curK - beta*uisroot + alpha) * (m-n+curK+1-uisroot)/(n2-n+curK+1-uisroot)

        tmp_p = np.append(tmp_p, new_root_wt)
        
        """ draw a new parent for u"""
        nbs.append(-1)
        myw = choices(nbs, weights=tmp_p)[0]
        
        if (myw == -1):
            myw = None
        
        graf.vs[u]["pa"] = myw
        
        if (myw == mypa):
            if (mypa != None):
                edge_ls.append((u, mypa))
            continue
        
        """ modifying pa, all_tree_degs """
        if (myw != None):
            all_tree_degs[myw] = all_tree_degs[myw] + 1
            if (not uisroot):
                all_tree_degs[mypa] = all_tree_degs[mypa] - 1
            else:
                # u was root, became non-root
                all_tree_degs[u] = all_tree_degs[u] + 1
                root_dict.pop(u)
                curK = curK - 1
            
            edge_ls.append((u, myw))
        else:
            ## u was not a root, became a root
            assert mypa != None
            root_dict[u] = 1
            curK = curK + 1
            all_tree_degs[u] = all_tree_degs[u] - 1
            all_tree_degs[mypa] = all_tree_degs[mypa] - 1


    assert len(edge_ls) == (n - curK)
    graf.es["tree"] = 0
    
    graf.es[graf.get_eids(edge_ls)]["tree"] = 1
    
    rootset = list(root_dict.keys())
    return(rootset)





def nodewiseSamplePA(graf, mypi, alpha, beta, K):
    """
    Generates new forest for a given ordering by sampling
    a new parent for each node. Used in fixed K setting.

    Require: graf.es has "tree" attribute

    Parameters
    ----------
    graf : igraph object
        Input graph; "tree" edge attribute and "pa" node
        attributes are modified in place.
    mypi : list
        Given ordering of the nodes.
    alpha : float
        Parameter.
    beta : float
        Parameter.
    K : int
        Num of clusters.

    Returns
    -------
    None.

    """
    n  = len(graf.vs)
    
    mypi_inv = [0] * n
    for i in range(n):
        mypi_inv[mypi[i]] = i

    for k in range(K):
        graf.vs[mypi[k]]["pa"] = None
        countSubtreeSizes(graf, mypi[k])

    all_tree_degs = getAllTreeDeg(graf)

    edge_ls = []
    
    for i in range(n-K):
        k = K+i
        v = mypi[k]
        
        mypa = graf.vs[v]["pa"]
        assert mypa is not None
        ## adjust parent degree
        all_tree_degs[mypa] = all_tree_degs[mypa] - 1
        
        nbs = graf.neighbors(v)
        nbs = [w for w in nbs if mypi_inv[w] < k]

        tree_degs = [all_tree_degs[w] for w in nbs]
        tree_degs = np.array(tree_degs)

        root_adj = np.array([w in mypi[0:K] for w in nbs])
        
        if (K == 1):
            root_adj = 0
        
        """ generate new parent for u"""
        tmp_p = beta*tree_degs + 2*beta*root_adj + alpha

        if (len(nbs) == 1):
            tmp_p = [1]

        myw = choices(nbs, weights=tmp_p)[0]

        edge_ls.append((v, myw))
        ## myw may potentially be mypa
        
        graf.vs[v]["pa"] = myw
        
        all_tree_degs[myw] = all_tree_degs[myw] + 1
        
    assert len(edge_ls) == (n - K)
    graf.es["tree"] = 0
    
    graf.es[graf.get_eids(edge_ls)]["tree"] = 1
    
    


def sampleOrdering(graf, tree2root, alpha, beta, DP=False):
    """
    Condition on the forest, generate a new root for each
    tree and generate a new global ordering.
    
    Require: graf.vs has "pa" attribute; graf.es has "tree" attribute

    Parameters
    ----------
    graf : igraph object
        Input graph; "pa" and "subtree_size" vertex attributes
        modified in place.
    tree2root : list
        list of root nodes.
    alpha : float
        Parameter.
    beta : float
        Parameter.
    DP : boolean, optional
        Use random K model or not. The default is False.

    Returns
    -------
    0. new node ordering
    1. list of new roots (only used in random K setting)

    """
    K = len(tree2root)
    n = len(graf.vs)
    
    time3 = time.time()
    
    degs = getAllTreeDeg(graf)
    
    mypi = [0] * n
    
    tree_sizes = getTreeSizes(graf, tree2root)
        
    """ draw new roots for each subtree """
    for k in range(K):
        if (tree_sizes[k] == 1):
            graf.vs[tree2root[k]]["subtree_size"] = 1
            mypi[k] = tree2root[k]                
            continue
        
        cur_root = tree2root[k]
        normalized_h = countAllHist(graf, cur_root)[0]
        
        assert( sum(normalized_h > 0) == tree_sizes[k] )
        
        deg_adj = (beta*degs + beta + alpha) * (beta*degs + alpha)
        if (K == 1):
            deg_adj = 1
        
        tmp_p = normalized_h*deg_adj
        
        mypi[k] = choices(range(n), tmp_p)[0]
        tree2root[k] = mypi[k]
        
        countSubtreeSizes(graf, root=mypi[k])
    
    if (DP):
        wts = [graf.vs[tree2root[k]]["subtree_size"] for k in range(K)]
        assert(sum(wts) == n)
        
        mypi[0] = tree2root[choices(range(K), wts)[0]]
        remain_nodes = [i for i in list(range(n)) if i != mypi[0]]
        assert mypi[0] not in remain_nodes
        
        mypi[1:n] = np.random.permutation(remain_nodes)
    else:
        remain_nodes = [i for i in list(range(n)) if i not in mypi[0:K]]
        mypi[K:n] = np.random.permutation(remain_nodes)
    
    mypi_inv = [0] * n
    for i in range(n):
        mypi_inv[mypi[i]] = i
    
    
    
    marked = {}
    
    if (DP):
        marked[mypi[0]] = 1
    else:
        for k in range(K):
            marked[mypi[k]] = 1
    
    for i in range(n-1):
        
        if (DP):
            k = 1 + i
        else:   
            k = K + i
            if (k >= n):
                break
            
        v = mypi[k]
        
        if (not DP): 
            assert v not in tree2root
            assert graf.vs[v]["pa"] != None
        
        if (v not in marked):
            ancs = getAncestors(graf, v)
            unmarked_ancs = [w for w in ancs if w not in marked]
            
            v_anc = unmarked_ancs[-1]            

            old_pos = mypi_inv[v_anc]
            mypi[old_pos] = v
            mypi[k] = v_anc
            mypi_inv[v_anc] = k
            mypi_inv[v] = old_pos
            
            marked[v_anc] = 1         
    
    if (DP):
        return((mypi, tree2root))    
    else:   
        return(mypi) 



def updateInferResults(graf, freq, tree2root, 
                       alpha, beta, size_thresh, birth_thresh,
                       node_tree_coo):
    """
    Match clustr-trees, update posterior root prob, and
    update node-tree co-occurrence results.
    
    Requires graf.vs has "pa" attribute.
    Requires graf.es has "tree" attribute.


    Parameters
    ----------
    graf : igraph object
        Input graph.
    freq : dict
        Existing posterior root probs; maps k to the 
        posterior root prob of tree k. Modified in place.
    tree2root : list
        list of root nodes.
    alpha : float
        Parameter.
    beta : float
        Parameter.
    size_thresh : float
        Thresh for keeping a cluster-tree. 
    birth_thresh : float
        Thresh for creating new distinct cluster-tree 
    node_tree_coo : nparray, optional
        (i,j)-th entry is num of times node i
        appears in tree j. The default is None.

    Returns
    -------
    nparray of new node-tree co-occurrences; replaces
    existing node_tree_coo.

    """
    n = len(graf.vs)
    
    sizes = getTreeSizes(graf, tree2root)
    sizes_sorted = -np.sort( - np.array(sizes))
    sizes_args = np.argsort( - np.array(sizes))

    K = len(tree2root)
    Kstar = len(freq)
    
    tree2root_sorted = [0] * len(tree2root)
    for k in range(K):
        tree2root_sorted[k] = tree2root[sizes_args[k]]
    
    cur_freq = {}
    treedegs = getAllTreeDeg(graf)
    
    for k in range(K):
        if (sizes_sorted[k] > size_thresh * n):
            cur_freq[k] = countAllHist(graf, tree2root_sorted[k])[0]
        else:
            break
        
        if (sizes_sorted[k] > 1):
            ## uncomment for exact credible root set
            ## cur_freq[k] = cur_freq[k] * (beta*treedegs+beta+alpha) \
            ##                    * (beta*treedegs + alpha)                           

            cur_freq[k] = cur_freq[k]/sum(cur_freq[k])
                    
    K = len(cur_freq)
    
    if (K > Kstar):
        for k in range(Kstar, K):
            freq[k] = np.array([0] * n)
            node_tree_coo = np.column_stack((node_tree_coo, np.zeros((n,1))))
        Kstar = K
        
    dists = np.zeros((K, Kstar))
    
    
    distr1_mat = np.zeros((Kstar, n))
    distr2_mat = np.zeros((K, n))

    for kstar in range(Kstar):
        if (sum(freq[kstar]) > 0):
            my_distr = np.array(freq[kstar]) 
            distr1_mat[kstar, :] = np.sqrt(my_distr/sum(my_distr))
        
    for k in range(K):
        my_distr = np.array(cur_freq[k]) 
        distr2_mat[k, :] = np.sqrt(my_distr/sum(my_distr))

    ## compute matrix of L2 distances between all rows of distr1_mat and distr2_mat
    dists = scipy.spatial.distance.cdist(distr2_mat, distr1_mat, 'sqeuclidean')
    dists = dists/2

    treematch = scipy.optimize.linear_sum_assignment(dists)[1]

    for k in range(K):
        if (dists[k, treematch[k]] > birth_thresh):
            freq[Kstar] = np.array([0] * n)
            treematch[k] = Kstar
            
            node_tree_coo = np.column_stack((node_tree_coo, np.zeros((n, 1))))
            Kstar = Kstar + 1
    
    for k in range(K):
        freq[treematch[k]] = freq[treematch[k]] + cur_freq[k]
      
    for ii in range(n):
        
        ants = getAncestors(graf, ii)
        myroot = ants[-1]
        my_k = tree2root_sorted.index(myroot)
        if (sizes_sorted[my_k] <= size_thresh * n):
            continue
                    
        my_kstar = treematch[my_k]
        node_tree_coo[ii, my_kstar] = node_tree_coo[ii, my_kstar] + 1     
    
    return(node_tree_coo)                    
        
        


def reorderSubvector(vec1, vec2, pos_dict):
    """

    Parameters
    ----------
    vec1 : list
        Longer input list.
    vec2 : list
        Shorter input list. Required to be a sub-list of
        vec1.
    pos_dict : dict
        Positions of all elements of vec2 in vec1. Modified in place.

    Returns
    -------
    a list which contains the same elements as vec1
    the sub-list that correspond to elements of vec2 is re-ordered
    according to vec2.

    """
    n = len(vec1)
    m = len(vec2)
    
    all_pos = [0] * m
    for i in range(m):
        all_pos[i] = pos_dict[vec2[i]]
    
    all_pos.sort()
        
    for i in range(m):
        vec1[all_pos[i]] = vec2[i]
        pos_dict[vec2[i]] = all_pos[i]
    
    return(vec1)











