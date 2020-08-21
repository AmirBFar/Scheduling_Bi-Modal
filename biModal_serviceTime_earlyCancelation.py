import simpy
from numpy.random import exponential, choice, binomial,  pareto, randint, seed
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import copy
import time
from operator import add
import sys
import math


class MGnQueue():
    
    def __init__(self, env, sRate, aRate, numberOfJobs, m, n, k, schPolicy, pEleph, rMice, rElephent, EtoMratio, alpha, sigma):
        self.env = env
        self.sRate = sRate
        self.singleQueue = simpy.Resource(self.env, capacity=1)
        self.aRate = aRate
        self.numberOfJobs = numberOfJobs

        self.alpha = alpha
        self.sigma = sigma

        self.m = m
        self.n = n
        self.k = k

        self.pEleph = pEleph
        self.rMice = rMice
        self.rElephent = rElephent
        self.EtoMratio = EtoMratio
        
        self.queueDict = {}
        for i in range(self.m):
            self.queueDict["queue%d"%i] = simpy.Resource(self.env, capacity=1)
        self.taskDict = {}
        self.requestDict = {}
        self.arrivalTimeDict = {}
        self.serviceTimeDict = {}
        self.systemTimeDict = {}

        self.jobCompletionTime = []
        self.departedJobs = []
        self.numberOfFinishedTasks = []
        self.finishedTasks = []
        self.scheduledQueues = []
        self.numberOfReplicas = [0 for i in range(10*numberOfJobs)]
        self.queuesLength = [0 for i in range(self.m)]
        
        self.action1 = self.env.process(self.arrivalGenerator())

        self.schPolicy = schPolicy
        self.sumService = 0
        self.jobGotToService = []
        self.miceCounter = 0
        self.processList = []
        self.tasksInService = [0 for i in range(self.numberOfJobs)]
        self.numJobsGotToService = [0 for i in range(self.m)]
        self.numJobsScheduled = [0 for i in range(self.m)]
        self.serviceTimes = []

    def __str__(self):
        return 'The average system time with arrival rate of '+str(self.aRate)+' and service rate of '+str(self.sRate)+' is '+str(sum(self.jobCompletionTime)/len(self.departedJobs))
        
        
    
    def arrivalGenerator(self):
        jobIndex = 0
        while jobIndex < self.numberOfJobs:
            self.service(jobIndex)
            yield self.env.timeout(exponential(1.0/self.aRate))
            jobIndex += 1

    def service(self,jobIndex):
        self.jobGotToService.append(False)
        self.arrivalTimeDict["task%d"%(jobIndex)] = self.env.now
        self.updateTaskDict_addTask(jobIndex)
        
        MiceOrElephent = binomial(1,self.pEleph)
        if MiceOrElephent == 0:
            MiceOrElephent = "Mice"
            self.numberOfReplicas[jobIndex] = self.rMice
        elif MiceOrElephent == 1:
            MiceOrElephent = "Elephent"
            self.numberOfReplicas[jobIndex] = self.rElephent

        if self.schPolicy == "random":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).random(jobIndex))
        elif self.schPolicy == "groupRandom":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).groupRandom())
        elif self.schPolicy == "JSQ":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).JSQ(jobIndex))
        elif self.schPolicy == "roundRobin":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).roundRobin(jobIndex))
        elif self.schPolicy == "BIBD_731":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).BIBD_731(jobIndex))
        elif self.schPolicy == "BIBD_843":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).BIBD_843(jobIndex))
        elif self.schPolicy == "BIBD_421":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).BIBD_421(jobIndex))
        elif self.schPolicy == "BIBD_1341":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).BIBD_1341(jobIndex))
        elif self.schPolicy == "BIBD_2151":
            self.scheduledQueues.append(scheduler(self.m, self.numberOfReplicas[jobIndex], self.queuesLength).BIBD_2151(jobIndex))

        processes = []
        idleQs = []
        for q in self.scheduledQueues[jobIndex]:
            if self.queuesLength[q] == 0:
                idleQs.append(q)
        if len(idleQs) != 0:
            q = idleQs[randint(len(idleQs))]
            self.processList.append(self.env.process(self.yieldProcessIdle(MiceOrElephent, jobIndex, q)))
            self.queuesLength[q] +=  1
            self.numJobsScheduled[q] += 1
        else:
            for taskIndex in range(self.numberOfReplicas[jobIndex]):
                if taskIndex == 0:
                    self.numberOfFinishedTasks.append(0)
                    self.finishedTasks.append([False for i in range(self.numberOfReplicas[jobIndex])])
                processes.append(self.env.process(self.yieldProcess(MiceOrElephent, jobIndex, taskIndex, self.scheduledQueues[jobIndex][taskIndex])))
                self.numJobsScheduled[self.scheduledQueues[jobIndex][taskIndex]] += 1
            self.queuesLength = [self.queuesLength[i]+1 if i in self.scheduledQueues[jobIndex] else self.queuesLength[i] for i in range(self.m)]  ## updating queue lenghts 
            self.processList.append(processes)
        return None
    
    def yieldProcess(self, MiceOrElephent, jobIndex, taskIndex, scheduledQueue):
        with self.queueDict["queue%d"%scheduledQueue].request() as req:
            self.requestDict["task%d%d"%(jobIndex,taskIndex)] = req
            try:
                startTime = self.env.now
                yield req
                endTime = self.env.now
                if self.jobGotToService[jobIndex] == False:
                    self.numJobsGotToService[scheduledQueue] += 1
                    #print(self.jobGotToService[jobIndex])
                    self.jobGotToService[jobIndex] = True
                    for task in range(self.n):
                        if task != taskIndex:
                            #print(jobIndex,taskIndex,task,self.jobGotToService[jobIndex],self.env.now)
                            sys.stdout.flush()
                            self.processList[jobIndex][task].interrupt("time to depart")
                    serviceTime = jobGenerator(self.k,jobIndex).Mice_Elephent_Exponential(MiceOrElephent, self.sRate, self.EtoMratio)
                    self.serviceTimes.append(serviceTime**2)
                    self.sumService += serviceTime
                    if MiceOrElephent == "Mice":
                        self.tasksInService[jobIndex] += 1
                    yield self.env.timeout(serviceTime)
                    self.departedJobs.append(jobIndex)
                    self.queuesLength[scheduledQueue] -= 1
                    self.jobCompletionTime.append(endTime -startTime)
            except simpy.Interrupt as i:
                pass

    def yieldProcessIdle(self, MiceOrElephent, jobIndex, scheduledQueue):
        with self.queueDict["queue%d"%scheduledQueue].request() as req:
            self.numJobsGotToService[scheduledQueue] += 1
            startTime = self.env.now
            serviceTime = jobGenerator(self.k,jobIndex).Mice_Elephent_Exponential(MiceOrElephent, self.sRate, self.EtoMratio)
            self.serviceTimes.append(serviceTime**2)
            self.sumService += serviceTime
            if MiceOrElephent == "Mice":
                self.tasksInService[jobIndex] += 1
            yield self.env.timeout(serviceTime)
            self.departedJobs.append(jobIndex)
            self.queuesLength[scheduledQueue] -= 1
            self.jobCompletionTime.append(0)
    
    def timeoutProcess(self, serviceTime, jobIndex, taskIndex):
        yield self.env.timeout(serviceTime)
        self.taskDict["%d%d"%(jobIndex,taskIndex)] = True
        self.serviceTimeDict["task%d%d"%(jobIndex,taskIndex)] =  serviceTime
        self.systemTimeDict["task%d%d"%(jobIndex,taskIndex)] = self.env.now - self.arrivalTimeDict["task%d"%(jobIndex)]

    def updateTaskDict_addTask(self, jobIndex):
        for taskIndex in range(self.n):
            self.taskDict["%d%d"%(jobIndex,taskIndex)] = False

    def jobDeparter(self, jobIndex, MiceOrElephent):
        while True:
            if True in self.taskDict.values():
                finishedTaskID = int(self.getKeyFromDict(True)[0])
                finishedTaskIndex = finishedTaskID%10
                finishedJobIndex = int(finishedTaskID/10)
                self.numberOfFinishedTasks[finishedJobIndex] += 1
                self.taskDict["%d%d"%(finishedJobIndex,finishedTaskIndex)] = False
                if self.finishedTasks[finishedJobIndex][finishedTaskIndex] == False:
                    self.finishedTasks[finishedJobIndex][finishedTaskIndex] = True
                    self.queuesLength[self.scheduledQueues[finishedJobIndex][finishedTaskIndex]] -= 1
                if self.numberOfFinishedTasks[finishedJobIndex] == self.k:
                    for taskIndex in range(self.numberOfReplicas[jobIndex]):
                        if self.finishedTasks[finishedJobIndex][taskIndex] == False:
                            self.finishedTasks[finishedJobIndex][taskIndex] = True
                            self.queuesLength[self.scheduledQueues[finishedJobIndex][taskIndex]] -= 1
                            self.queueDict["queue%d"%self.scheduledQueues[finishedJobIndex][taskIndex]].release(self.requestDict["task%d%d"%(finishedJobIndex,taskIndex)])
                    if True:
                        self.jobCompletionTime.append(self.systemTimeDict["task%d%d"%(finishedJobIndex,finishedTaskIndex)])
                        self.miceCounter += 1
            else:
                break
        return None
                
    def getKeyFromDict(self, BOOL):
        return [taskID for taskID, bool in self.taskDict.items() if bool == BOOL]

class jobGenerator():
    def __init__(self,k,jobIndex):
        self.k = k

    def Exponential(self,mu):
        return exponential(1.0/(self.k*mu))

    def Mice_Elephent_Exponential(self,MiceOrElephent,muMice,EtoMratio):
        if MiceOrElephent == "Mice":
            serviceTime = exponential(1.0/(self.k*muMice))
        elif MiceOrElephent == "Elephent":
            serviceTime = EtoMratio*exponential(1.0/(self.k*muMice))
        return serviceTime

    def Pareto(self,alpha,sigma):
        return pareto(alpha)+sigma

    def Mice_Elephent_Pareto(self,MiceOrElephent,alpha,sigma,pEleph,EtoMratio):
        if MiceOrElephent == "Mice":
            serviceTime = self.Pareto(alpha,sigma)
        elif MiceOrElephent == "Elephent":
            serviceTime = EtoMratio*self.Pareto(alpha,sigma)
        return serviceTime

class scheduler():
    def __init__(self, m, n, queuesLength):
        self.m = m
        self.n = n
        
        self.queuesLength = queuesLength

    def random(self,jobIndex):
        selectedQueues = list(choice(self.m, self.n, replace=False))
        return selectedQueues

    def groupRandom(self):
        rndGroupIndex = randint(0,self.m/self.n)
        return [rndGroupIndex*self.n+j for j in range(self.n)]

    def JSQ(self,jobIndex):
        shortestQueues = []
        CPY_queuesLength = copy.copy(self.queuesLength)
        for i in range(self.n):
            shortestQueues.append(CPY_queuesLength.index(min(CPY_queuesLength)))
            CPY_queuesLength[CPY_queuesLength.index(min(CPY_queuesLength))] = float("inf")
        return shortestQueues

    def roundRobin(self,jobIndex):
        return [(self.n*jobIndex+j)%(self.m) for j in range(self.n)]

    def BIBD_731(self, jobIndex):
        bibd = [[0,1,2],[1,3,5],[2,3,6],[0,5,6],[1,4,6],[0,3,4],[2,4,5]]
        return bibd[jobIndex%7]

    def BIBD_843(self, jobIndex):
        bibd = [[0,1,2,3],[0,1,2,4],[0,1,5,6],[0,2,5,7],[0,3,4,5],[0,3,6,7],[0,4,6,7],[1,2,6,7],[1,3,4,6],[1,3,5,7],[1,4,5,7],[2,3,4,7],[2,3,5,6],[2,4,5,6]]
        return bibd[jobIndex%14]

    def BIBD_421(self, jobIndex):
        bibd = [[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]]
        return bibd[jobIndex%6]

    def BIBD_821(self, jobIndex):
        bibd = [[0,1],[0,2],[0,3],[0,4],[0,5],[0,6],[0,7],[1,2],[1,3],[1,4],[1,5],[1,6],[1,7],[2,3],[2,4],[2,5],[2,6],[2,7],[3,4],[3,5],[3,6],[3,7],[4,5],[4,6],[4,7],[5,6],[5,7],[6,7]]
        #return bibd[jobIndex%28]
        return bibd[randint(28)]

    def BIBD_1341(self, jobIndex):
        bibd = [[0,1,2,3],[0,4,5,6],[0,7,8,9],[0,10,11,12],[1,4,7,10],[1,5,8,11],[1,6,9,12],[2,4,8,12],[3,4,9,11],[3,5,7,12],[3,6,8,10],[2,5,9,10],[2,6,7,11]]
        return bibd[jobIndex%13]

    def BIBD_2151(self, jobIndex):
        bibd = [[1,5,6,9,10],[2,6,14,19,20],[0,2,4,5,8],[5,11,13,18,19],[0,10,11,12,14],[4,9,14,15,18],[0,9,13,17,20],[7,8,10,18,20],[6,8,11,15,17],[4,6,7,12,13],[5,7,14,16,17],[8,9,12,16,19],[3,5,12,15,20],[3,4,10,17,19],[2,3,7,9,11],[0,3,6,16,18],[2,10,13,15,16],[1,4,11,16,20],[1,3,8,13,14],[1,2,12,17,18],[0,1,7,15,19]]
        return bibd[jobIndex%21]
class queueRunner(object):
    def __init__(self, sRate, aRateVector, numberOfJobs, m, n, k):
        self.sRate = sRate
        self.aRateVector = aRateVector
        self.numberOfJobs = numberOfJobs

        self.m = m
        self.n = n
        self.k = k

        self.env = simpy.Environment()

        self.avgCompletionTimes = []
        self.avgNumTasksInService = []
        self.avgCancellation = []
        self.avgServiceTime = []

    def runner(self, schPolicy, alpha, sigma, EtoMratio, pEleph):
        rMice, rElephent = self.n, self.n
        for aRate in self.aRateVector:
            print(aRate)
            sys.stdout.flush()
            Queue = MGnQueue(self.env, self.sRate, aRate, self.numberOfJobs, self.m, self.n, self.k, schPolicy, pEleph, rMice, rElephent, EtoMratio, alpha, sigma)
            self.env.run()
            self.avgCompletionTimes.append(1.0*sum(Queue.jobCompletionTime)/len(Queue.jobCompletionTime))
            self.avgCancellation.append(Queue.numJobsGotToService[0]/Queue.numJobsScheduled[0])
            self.avgServiceTime.append(sum(Queue.serviceTimes)/len(Queue.serviceTimes))
            newList = [x for x in Queue.tasksInService if x>0]
            self.avgNumTasksInService.append(1.0*sum(newList)/len(newList))
        print("average completion time for %s is"%schPolicy, self.avgCompletionTimes)
        return self.avgCompletionTimes, self.avgCancellation, self.avgServiceTime

    def plotGenerator(self):
        plt.plot([(i+1) for i in range(8)], self.avgCompletionTimes,'--bo')
        plt.xlabel('Arrival rate')
        plt.ylabel('Average job completion time')
        plt.yscale('log')
        plt.title('Arrival rate=%.1f, m=%d, n=%d, k=%d'%(self.aRate,self.m,self.n,self.k))
        plt.show()

def NchooseK(a,b):
    result = factorial(a)/(factorial(b)*factorial(a-b))
    return result

def factorial(X):
    fact = 1
    for j in range(X):
        fact = fact*(j+1)
    return fact

def bibdApprox(q,pEleph,mu,n,lam):
    lam = 2.0*lam/(1.0*n)
    ET = (1 + (q-1.0)*pEleph)/(2.0*mu)
    ET2 = 1.0*(1.0+(q**2-1.0)*pEleph)/(mu**2)
    #ETQ = ET + lam*ET2/(2.0*(1-lam*ET))
    #return ETQ - math.sqrt(ETQ**2 + (1+(q**3-1)*pEleph))
    #ET2 = (1 + (q**2-1.0)*pEleph)*(1.0/(2*mu**2)+.5*ET**2)
    #return (1+(q-1)*pEleph)/(2*mu) + (2.0*lam/(2*n)) * ((1+(q**2-1)*pEleph)/(2*mu**2)) / (1-(2.0*lam/(2*n*mu))*(1+(q-1)*pEleph))
    #return ET + lam*ET2/(2.0*(1-lam*ET))
    return ((1+math.sqrt(7))*lam)/(2*math.sqrt(7)*(7*mu-lam)*(mu))

def mg2QTime(q,pEleph,mu,n,lam):
    ET = (1 + (q-1.0)*pEleph)/(1.0*mu)
    ET2 = 2.0*(1 + (q**2-1)*pEleph)/(1.0*mu**2)
    rho = lam*ET/n
    summation = sum([((2*rho)**k)/factorial(k) for k in range(2)])
    mgn = (ET2/(2*ET**2)) * (1.0/((2/ET-2*lam/n)*(1+(1-rho)*(factorial(2)/((2*rho)**2))*summation)))
    return mgn

def mgnQTime(q,pEleph,mu,n,r,lam):
    #lam = 1.0*r*lam/n
    #ET = (1 + (q-1.0)*pEleph)/(1.0*r*mu)
    #ET2 = (1 + (q**2-1.0)*pEleph)*(2.0/(r*mu**2))
    #rho = lam*ET/r
    r=7
    ET = (1 + (q-1.0)*pEleph)/(1.0*mu)
    ET2 = (1 + (q**2-1.0)*pEleph)*(2.0/(mu**2))
    rho = lam*ET/n
    summation = sum([((r*rho)**k)/factorial(k) for k in range(r)])
    mgn = (ET2/(2*ET**2)+0.5) * (1.0/((r/ET-1.0*r*lam/n)*(1+(1-rho)*(factorial(r)/((r*rho)**r))*summation)))
    return mgn

def mg1QTime(q,pEleph,mu,n,r,lam):
    lam = 1.0*lam/n
    ET = (1 + (q-1.0)*pEleph)/(1.0*mu)
    ET2 = (1 + (q**2-1)*pEleph)*(2.0/(mu**2))
    return lam*ET2/(2.0*(1-lam*ET))

def avgResTime(q,pEleph,mu):
    return (1 + (q-1.0)*pEleph)/(1.0*mu)

if __name__ == '--main__':
    start = time.time()

    sRate = 10
    alpha = 1
    sigma = 1

    numberOfJobs = 20000
    m = 7
    n = 3
    k = 1
    numIter = 1
    pEleph = .1
    rMice = n
    EtoMratio = 1


    q = EtoMratio
    maxRate = (m*sRate)/(1+(q-1)*pEleph)
    step = maxRate/20.0
    initVal = 0
    aRateVector = [initVal+(i+1)*step for i in range(18)]
    Ca_2 = 1.0*n/m
    Cs_2 = 1.0*(1+(q-1)*(2*q-(q-1)*pEleph)*pEleph)/((1+(q-1)*pEleph)**2)
    rho = [(1.0*lam/(m*sRate))*(1+(q-1)*pEleph) for lam in aRateVector]
    print("this is rho", rho)
    tau = (1+(q-1)*pEleph)/(n*sRate)
    rrApprox = [1.0/(n*sRate)+(x/(1-x))*((Ca_2+Cs_2)/2)*tau for x in rho]

    groupRandomFormula = [1.0/(n*sRate) + (1+(q**2-1)*pEleph)/(1.0*m*n*(sRate)**2/lam - 1.0*n*sRate*(1+(q-1)*pEleph)) for lam in aRateVector]

    randomAnalysis = []
    bibdApp = []
    randomServiceTimeAnalysis = []
    for lam in aRateVector:
        randomAnalysis.append(sum([1.0/(1.0*m*sRate*NchooseK(m-1,n-1)/NchooseK(i-1,n-1) - lam) for i in range(n,m+1)]))
        bibdApp.append(bibdApprox(q,pEleph,sRate,m,lam))
        #bibdApp.append(avgResTime(q,pEleph,sRate) + (mg2QTime(q,pEleph,sRate,m,lam)/mg1QTime(q,pEleph,sRate,m,lam))*mg1QTime(q,pEleph,sRate,m,lam))
        #bibdApp.append(mg1QTime(q,pEleph,sRate,m,n,lam)) 
        randomServiceTimeAnalysis.append(1.0*(1 + (q-1.0)*pEleph)/(1.0*sRate))

    bibdNumTasks = [0 for i in range(len(aRateVector))]
    rrNumTasks = [0 for i in range(len(aRateVector))]
    randomNumTasks = [0 for i in range(len(aRateVector))]

    JSQTime = [0 for i in range(len(aRateVector))]
    rrTime = [0 for i in range(len(aRateVector))]
    randomTime = [0 for i in range(len(aRateVector))]
    bibdTime = [0 for i in range(len(aRateVector))]
    groupRandomTime = [0 for i in range(len(aRateVector))]

    randomServiceTime = [0 for i in range(len(aRateVector))]

    for i in range(numIter):
        stTime = time.time()
        rrResults = queueRunner(sRate, aRateVector, numberOfJobs, m, n, k).runner("roundRobin", alpha, sigma, EtoMratio, pEleph)
        rrTime = list(map(add,rrTime,rrResults[0]))
        #JSQResults =queueRunner(sRate, aRateVector, numberOfJobs, m, n, k).runner("JSQ", alpha, sigma, EtoMratio, pEleph)
        #JSQTime = list(map(add,JSQTime,JSQResults[0]))
        randomResults =queueRunner(sRate, aRateVector, numberOfJobs, m, n, k).runner("random", alpha, sigma, EtoMratio, pEleph)
        randomTime = list(map(add,randomTime,randomResults[0]))
        bibdResults =queueRunner(sRate, aRateVector, numberOfJobs, m, n, k).runner("BIBD_731", alpha, sigma, EtoMratio, pEleph)
        bibdTime = list(map(add,bibdTime,bibdResults[0]))

        bibdNumTasks = list(map(add,bibdNumTasks,bibdResults[1]))
        rrNumTasks = list(map(add,rrNumTasks,rrResults[1]))
        randomNumTasks = list(map(add,randomNumTasks,randomResults[1]))

        randomServiceTime = list(map(add,randomServiceTime,randomResults[2]))
        print("iteration %d is done out of %d in %.2f seconds"%(i+1,numIter,time.time()-stTime))

    JSQTime = [1.0*T/numIter for T in JSQTime]
    rrTime = [1.0*T/numIter for T in rrTime]
    randomTime = [1.0*T/numIter for T in randomTime]
    bibdTime = [1.0*T/numIter for T in bibdTime]

    bibdNumTasks = [1.0*T/numIter for T in bibdNumTasks]
    rrNumTasks = [1.0*T/numIter for T in rrNumTasks]
    randomNumTasks = [1.0*T/numIter for T in randomNumTasks]
    print("Total execution time is %.2f"%(time.time()-start))


    lowTraf = [lam for lam in aRateVector[:12]]
    plt.figure(1)
    fig, axes = plt.subplots(1,2, figsize=[12, 5])
    #plt.setp(axes.flat, aspect=1.0, adjustable='box-forced')
    rnd,= axes[0].plot(lowTraf, randomTime[:12], color='blue', marker='s', linestyle='dotted', label="Random",markersize=10,linewidth=2)
    rr,= axes[0].plot(lowTraf, rrTime[:12], color='green', marker='D', linestyle='dotted', label="Round-Robin",markersize=10,linewidth=2)
    bibd,= axes[0].plot(lowTraf, bibdTime[:12], color='orange', marker='x', linestyle='dotted', mew=3, label="BIBD (%d,%d,1)"%(m,n),markersize=10,linewidth=2)
    #jsq,= plt.plot(lowTraf, JSQTime[:12],'--cv', label="JSQ")
    bibdapx, = axes[0].plot(lowTraf, bibdApp[:12], color='red', marker='+', linestyle='dotted', label='Block design approx.')
    #rrapx, = plt.plot(aRateVector, rrApprox, '--mp', label="Round-Robin approximation")
    #grprnd, = plt.plot(aRateVector, groupRandomFormula, '--k*', label="Group random")
    #rndan, =  plt.plot(aRateVector, randomAnalysis, '--m+', label="Random analysis") 
    axes[0].legend(handles=[rnd,rr,bibd,bibdapx], loc=0)
    axes[0].set_xlabel(r'Arrival rate ($\lambda$)',fontsize=12)
    axes[0].set_ylabel('Average queuing time',fontsize=12)
    #axes[0].set_aspect('equal')
    #axes[0].ylabel('Average job completion time')
    #plt.title(r'Service rate=%.1f, n=%d, r=%d, q=%d, $P_{\epsilon}=%.2f$'%(sRate,m,n,EtoMratio,pEleph))
    #plt.savefig("result_%d_jobs_%d_q_%.1f_Pe.png"%(numberOfJobs,EtoMratio,pEleph))
    #plt.show()


    highTraf = [lam for lam in aRateVector[12:]]
    rnd,= axes[1].plot(highTraf, randomTime[12:],color='blue', marker='s', linestyle='dotted', label="Random",markersize=10,linewidth=2)
    rr,= axes[1].plot(highTraf, rrTime[12:], color='green', marker='D', linestyle='dotted', label="Round-Robin",markersize=10,linewidth=2)
    bibd,= axes[1].plot(highTraf, bibdTime[12:],color='orange', marker='x', linestyle='dotted', mew=3, label="BIBD (%d,%d,1)"%(m,n),markersize=10,linewidth=2)
    bibdapx, = axes[1].plot(highTraf, bibdApp[12:], color='red', marker='+', linestyle='dotted', label='Block design approx.')
    #jsq,= plt.plot(highTraf, JSQTime[12:],'--cv', label="JSQ")
    #rrapx, = plt.plot(aRateVector, rrApprox, '--mp', label="Round-Robin approximation")                                                                         
    #grprnd, = plt.plot(aRateVector, groupRandomFormula, '--k*', label="Group random")
    #rndan, =  plt.plot(aRateVector, randomAnalysis, '--m+', label="Random analysis")                                                                         
    axes[1].legend(handles=[rnd,rr,bibd,bibdapx], loc=0)
    axes[1].set_xlabel(r'Arrival rate ($\lambda$)',fontsize=12)
    #axes[1].set('equal')
    #plt.ylabel('Averagen number of tasks get into service')
    #plt.yscale('log')                                                                                                                                            
    #plt.title(r'Service rate=%.1f, n=%d, r=%d, q=%d, $P_{\epsilon}=%.2f$'%(sRate,m,n,EtoMratio,pEleph))
    plt.suptitle(r'$(n,r,\mu_1,q,p)=(%d,%d,%d,%d,%.1f)$'%(m,n,sRate,EtoMratio,pEleph),fontsize=18)
    plt.savefig("result_%d_jobs_q_%d_Pe_%.1f_n_%d_r_%d.png"%(numberOfJobs,EtoMratio,pEleph,m,n))
    plt.show()
            
    '''
    plt.figure(3)
    rnd,= plt.plot(aRateVector, randomServiceTime,'--bo', label="Random")
    rndan,= plt.plot(aRateVector, randomServiceTimeAnalysis,'--k*', label="Random analysis")
    plt.legend(handles=[rnd,rndan], loc=0)
    plt.xlabel('Arrival rate')
    plt.ylabel('Average service time')
    #plt.yscale('log')                                                                                                                                                                                                
    plt.title(r'Service rate=%.1f, n=%d, r=%d, q=%d, $P_{\epsilon}=%.2f$'%(sRate,m,n,EtoMratio,pEleph))
    plt.savefig("result2_%d_jobs_%d_q_%.1f_Pe.png"%(numberOfJobs,EtoMratio,pEleph))
    plt.show()
    '''         
        
